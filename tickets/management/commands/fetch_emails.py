import imaplib
import email
from email.header import decode_header
from django.core.management.base import BaseCommand
from django.conf import settings
from tickets.models import Ticket, Usuario
import unicodedata
import re

def limpiar_texto(texto):
    if not texto:
        return ''
    texto = unicodedata.normalize('NFC', texto)
    
    texto_limpio = ''.join(
        ch for ch in texto 
        if unicodedata.category(ch) not in ['Cf', 'Co', 'Cn'] or ch in ['\n', '\r', '\t']
    )
    
    return texto_limpio.encode('utf-8', 'ignore').decode('utf-8', 'ignore')

class Command(BaseCommand):
    help = 'Obtiene correos electrónicos mediante IMAP y los registra como tickets.'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando la lectura de correos...'))
    
        IMAP_SERVER = getattr(settings, 'IMAP_SERVER', 'mail.grupoloscar.net')
        IMAP_PORT = getattr(settings, 'IMAP_PORT', 993)
        IMAP_USER = getattr(settings, 'IMAP_USER', 'deivy.delgado@grupoloscar.net')
        IMAP_PASSWORD = getattr(settings, 'IMAP_PASSWORD', 'Deivy2026*')

        try:
            correo = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            correo.login(IMAP_USER, IMAP_PASSWORD)
            correo.select('INBOX')
            
            status, messages = correo.search(None, 'UNSEEN')
            correo_ids = messages[0].split()
            
            self.stdout.write(f'Correos no leídos encontrados: {len(correo_ids)}')
            
            if not correo_ids:
                self.stdout.write(self.style.WARNING('No se encontraron correos nuevos para procesar.'))
                correo.logout()
                return
            
            usuario_admin = Usuario.objects.filter(rol='admin').first() or Usuario.objects.first()
            
            for e_id in correo_ids:
                try:
                    status, msg_data = correo.fetch(e_id, '(RFC822)')
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Decodificar Asunto
                            subject_header = msg.get('Subject', '(Sin Asunto)')
                            subject_decoded, encoding = decode_header(subject_header)[0]
                            if isinstance(subject_decoded, bytes):
                                subject = subject_decoded.decode(encoding or 'utf-8', errors='ignore')
                            else:
                                subject = str(subject_decoded)
                                
                            from_header = msg.get('From', '')
                            email_remitente = email.utils.parseaddr(from_header)[1]
                            
                            creado_por_user = Usuario.objects.filter(correo=email_remitente).first()
                            if not creado_por_user:
                                creado_por_user = usuario_admin
                                
                            cuerpo = ''
                            
                            if msg.is_multipart():
                                for part in msg.walk():
                                    content_type = part.get_content_type()
                                    content_disposition = str(part.get('Content-Disposition'))
                                    if content_type == 'text/plain' and 'attachment' not in content_disposition:
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            charset = part.get_content_charset() or 'utf-8'
                                            cuerpo = payload.decode(charset, errors='ignore')
                                        break
                            else:
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    charset = msg.get_content_charset() or 'utf-8'
                                    cuerpo = payload.decode(charset, errors='ignore')
                                            
                            # Sanatizar asunto y cuerpo
                            subject_clean = limpiar_texto(subject)
                            cuerpo_clean = limpiar_texto(cuerpo)
                            
                            self.stdout.write(f'Procesando correo de: {from_header} - Asunto: {subject_clean}')
                                
                            ticket = Ticket.objects.create(
                                asunto=subject_clean,
                                descripcion=f'De: {from_header}\n\nContenido:\n{cuerpo_clean if cuerpo_clean else "Sin contenido de texto"}',
                                creado_por=creado_por_user
                            )
                            self.stdout.write(self.style.SUCCESS(f'Ticket #{ticket.id_ticket} creado exitosamente'))
                except Exception as inner_e:
                    self.stderr.write(self.style.ERROR(f'Error al procesar correo ID {e_id}: {inner_e}'))
                    continue
                    
            correo.logout()
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error durante el procesamiento: {e}'))