import imaplib
import email
import datetime
from email.header import decode_header
import unicodedata
from django.conf import settings
from bs4 import BeautifulSoup
from email.utils import parseaddr
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets, status, permissions
from django.db.models import Q
from .models import Ticket, Usuario, RespuestaTicket
from .serializers import TicketSerializer, RegistroSerializer, UsuarioSerializer, RespuestaTicketSerializer
from django.core.mail import EmailMessage, get_connection

def limpiar_texto(texto):
    if not texto:
        return ''
    texto = unicodedata.normalize('NFC', texto)
    texto_limpio = ''.join(
        ch for ch in texto 
        if unicodedata.category(ch) not in ['Cf', 'Co', 'Cn'] or ch in ['\n', '\r', '\t']
    )
    return texto_limpio.encode('utf-8', 'ignore').decode('utf-8', 'ignore')

class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'put', 'delete']
    
    def get_queryset(self):
        usuario = self.request.user
        rol = getattr(usuario, 'rol', None)
        
        # Ver todo
        if rol == 'superuser':
            return Ticket.objects.all()
        
        filtro_q = Q(creado_por=usuario) | Q(asignado_a=usuario) | Q(colaborador=usuario)
        
        if usuario.correo:
            filtro_q |= Q(para__icontains=usuario.correo)

        # Usuario  estandar
        return Ticket.objects.filter(filtro_q).distinct()
            
@api_view(['POST'])
@permission_classes([AllowAny])
def registrar_usuario(request):
    serializer = RegistroSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Usuario registrado exitosamente."},
            status=status.HTTP_201_CREATED
        )
    print("ERRORES DRF:", serializer.errors)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

DOMINIOS_ESPECIALES = {
    'gmail.com': 'imap.gmail.com',
    'outlook.com': 'outlook.office365.com',
}

def obtener_servidor_mail(correo_usuario):
    if not correo_usuario or '@' not in correo_usuario:
        return getattr(settings, 'IMAP_SERVER', 'mail.grupoloscar.net')
    
    dominio = correo_usuario.split('@')[-1].lower().strip()
    return DOMINIOS_ESPECIALES.get(dominio, f'mail.{dominio}')
    
@api_view(['POST'])
@permission_classes([AllowAny])
def verificar_correo_imap(request):
    correo = request.data.get('correo')
    password = request.data.get('password')
    
    if not correo or not password:
        return Response(
            {'error': 'Se requiere el correo y la contraseña'},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    imap_server = obtener_servidor_mail(correo)
    imap_port = getattr(settings, 'IMAP_PORT', 993)
    
    try:
        mail_connection = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail_connection.login(correo, password)
        mail_connection.logout()
        
        return Response({
            'message': f'Conexión exitosa con {imap_server} para {correo}'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': f'Error de autenticación IMAP en {imap_server}: {str(e)}'}, status=status.HTTP_401_UNAUTHORIZED)
    
def sync_user_emails(usuario, password_imap=None):    
    if not usuario.correo:
        return 0
    
    IMAP_SERVER = obtener_servidor_mail(usuario.correo)
    IMAP_PORT = getattr(settings, 'IMAP_PORT', 993)
    IMAP_USER = usuario.correo
    IMAP_PASSWORD = password_imap
    if not IMAP_PASSWORD:
        print(f"Sincronización omitida para {usuario.correo}: No seproporcionó clave IMAP.")
    
    ticket_creado = 0
    
    try: 
        correo = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        correo.login(IMAP_USER, IMAP_PASSWORD)
        correo.select('INBOX')
            
        hace_7_dias = datetime.datetime.now() - datetime.timedelta(days=7)
        meses_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        desde_fecha = f"{hace_7_dias.day:02d}-{meses_en[hace_7_dias.month - 1]}-{hace_7_dias.year}"
        
        status_code, messages = correo.search(None, f'SINCE {desde_fecha}')
        correo_ids = messages[0].split()
        
        if not correo_ids:
            correo.logout()
            return 0
        
        for e_id in correo_ids:
            try:
                _, msg_data = correo.fetch(e_id, '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT FROM TO)])')
                header_text = msg_data[0][1].decode('utf-8', errors='ignore')
                msg_id = None
                para_header = ''

                for line in header_text.splitlines():
                    if line.lower().startswith('message-id:'):
                        msg_id = line.split(':', 1)[1].strip('<> \r\n\t')
                    elif line.lower().startswith('to:'):
                        raw_para = line.split(':', 1)[1].strip()
                        _, correo_limpio = parseaddr(raw_para)
                        para_header = correo_limpio.lower() if correo_limpio else raw_para

                if not msg_id:
                    msg_id = f"custom_{e_id.decode()}_{usuario.id_usuario}"
                    
                if Ticket.objects.filter(message_id=msg_id).exists():
                    continue
                
                _, full_msg_data = correo.fetch(e_id, '(RFC822)')
                
                for response_part in full_msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Decodificación del Asunto
                        subject_header = msg.get('Subject', '')
                        if subject_header:
                            subject_parts = decode_header(subject_header)
                            subject_decoded, encoding = subject_parts[0]
                            if isinstance(subject_decoded, bytes):
                                subject = subject_decoded.decode(encoding or 'utf-8', errors='ignore')
                            else:
                                subject = str(subject_decoded)
                        else:
                            subject = 'Sin Asunto'

                        subject_clean = limpiar_texto(subject).strip()
                        from_header = msg.get('From', '')

                        if 'mailer_daemon' in from_header.lower() or 'postmaster' in from_header.lower():
                            continue

                        # Remitente (Creado Por)
                        nombre_remitente, correo_remitente = parseaddr(from_header)
                        correo_remitente = correo_remitente.lower().strip()

                        if correo_remitente:
                            username_base = correo_remitente.split('@')[0]
                            usuario_remitente, created = Usuario.objects.get_or_create(
                                correo=correo_remitente,
                                defaults={
                                    'nombre': nombre_remitente if nombre_remitente else username_base,
                                    'usuario_seccion': correo_remitente
                                }
                            )
                            if not created and nombre_remitente and usuario_remitente.nombre != nombre_remitente:
                                usuario_remitente.nombre = nombre_remitente
                                usuario_remitente.save(update_fields=['nombre'])
                        else:
                            usuario_remitente = usuario

                        # Extraer Cuerpo e Imagen Adjunta
                        cuerpo = ''
                        imagen_adjunta = None
                        nombre_imagen = None

                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get('Content-Disposition'))
                                content_id = part.get('Content-ID')

                                # Capturar cuerpo
                                if content_type == 'text/plain' and 'attachment' not in content_disposition and not cuerpo:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        charset = part.get_content_charset() or 'utf-8'
                                        cuerpo = payload.decode(charset, errors='ignore')
                                elif content_type == 'text/html' and not cuerpo and 'attachment' not in content_disposition:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        charset = part.get_content_charset() or 'utf-8'
                                        html_raw = payload.decode(charset, errors='ignore')
                                        soup = BeautifulSoup(html_raw, 'html.parser')
                                        for script in soup(["script", "style"]):
                                            script.decompose()
                                        cuerpo = soup.get_text(separator='\n').strip()

                                # Capturar imagen si viene adjunta o incrustada
                                if content_type.startswith('image/') and not imagen_adjunta:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        filename = part.get_filename() 
                                        if not filename:
                                            ext = content_type.split('/')[-1]
                                            filename = f'inline_{msg_id}.{ext}'
                                            
                                        nombre_imagen = filename
                                        imagen_adjunta = ContentFile(payload, name=filename)

                        else:
                            content_type = msg.get_content_type()
                            payload = msg.get_payload(decode=True)
                            if payload:
                                charset = msg.get_content_charset() or 'utf-8'
                                raw_text = payload.decode(charset, errors='ignore')
                                if content_type == 'text/html':
                                    soup = BeautifulSoup(raw_text, 'html.parser')
                                    for script in soup(["script", "style"]):
                                        script.extract()
                                    cuerpo = soup.get_text(separator='\n').strip()
                                else:
                                    cuerpo = raw_text

                        cuerpo_clean = limpiar_texto(cuerpo)
                        
                        # Crear la instancia del ticket
                        ticket = Ticket(
                            message_id=msg_id,
                            para=para_header or usuario.correo,
                            asunto=subject_clean,
                            descripcion=cuerpo_clean if cuerpo_clean else "Sin contenido de texto",
                            creado_por=usuario_remitente,
                            asignado_a=usuario # Se asigna al usuario con el que se inició sesión
                        )

                        if imagen_adjunta:
                            ticket.imagen.save(nombre_imagen, imagen_adjunta, save=False)

                        ticket.save()
                        ticket_creado += 1

            except Exception as ex:
                print(f"Error procesando correo ID {e_id}: {ex}")
                continue
                
        correo.logout()
    except Exception as e:
        print(f'Error sincronizando IMAP para {usuario.correo}: {e}')
        
    return ticket_creado

@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def sync_and_list_tickets(request):
    usuario = request.user
    
    password_imap = request.data.get('password_imap') or request.headers.get('X-IMAP-Password') or request.session.get('imap_password')
    
    if usuario.correo:
        sync_user_emails(usuario, password_imap=password_imap)

    rol = getattr(usuario, 'rol', None)
    
    if rol == 'superuser':
        tickets = Ticket.objects.all()
    else:
        filtro_q = Q(creado_por=usuario) | Q(asignado_a=usuario) | Q(colaborador=usuario)
        
        if usuario.correo:
            filtro_q |= Q(para__icontains=usuario.correo)
        
        tickets = Ticket.objects.filter(filtro_q).distinct()
        
    serializer = TicketSerializer(tickets, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obtener_usuarios(request):
    usuarios = Usuario.objects.all()
    serializer = UsuarioSerializer(usuarios, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def responder_ticket(request, pk):
    try:
        ticket = Ticket.objects.get(pk=pk)
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    
    contenido = request.data.get('contenido', '').strip()
    es_nota = request.data.get('es_nota', False)
    
    if not contenido:
        return Response({'error': 'El mensaje no puede estar vacio.'}, status=status.HTTP_400_BAD_REQUEST)
    
    respuesta_obj = RespuestaTicket.objects.create(
        ticket=ticket,
        usuario=request.user,
        contenido=contenido,
        es_nota_interna=es_nota
    )
    
    if not es_nota:
        destinatario = ticket.creado_por.correo if ticket.creado_por and ticket.creado_por.correo else None
    
        if destinatario:
            usuario_actual = request.user
            remitente = usuario_actual.correo or ticket.para
            
            # Obtener credenciales dinámicas del usuario autenticado
            smtp_host = obtener_servidor_mail(remitente)
            smtp_port = getattr(settings, 'SMTP_PORT', 465)  
            smtp_password = getattr(request, 'user_smtp_password', getattr(settings, 'IMAP_PASSWORD', 'Deivy2026*'))

            asunto_correo = f'Re: [{ticket.id_ticket}] {ticket.asunto}'
            
            headers_mail = {}
            if ticket.message_id:
                headers_mail['In-Reply-To'] = f'<{ticket.message_id}>'
                headers_mail['References'] = f'<{ticket.message_id}>'
                
            try:
                es_puerto_ssl = smtp_port == 465
                
                connection = get_connection(
                    backend='django.core.mail.backends.smtp.EmailBackend',
                    host=smtp_host,
                    port=smtp_port,
                    username=remitente,
                    password=smtp_password,
                    use_ssl=es_puerto_ssl,
                    use_tls= not es_puerto_ssl,
                    timeout=10, 
                    fail_silently=False
                )

                email_msg = EmailMessage(
                    subject=asunto_correo,
                    body=contenido,
                    from_email=remitente,
                    to=[destinatario],
                    headers=headers_mail,
                    connection=connection
                )
                
                email_msg.send(fail_silently=False)
            except Exception as e:
                print(f'Error enviando correo SMTP para {remitente}: {e}')
                
    serializer = RespuestaTicketSerializer(respuesta_obj)
    return Response(serializer.data, status=status.HTTP_201_CREATED)