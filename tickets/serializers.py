from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import Ticket, Usuario, RespuestaTicket

class UsuarioMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model=Usuario
        fields=['id_usuario','usuario_seccion','nombre', 'correo', 'rol']
        
class RespuestaTicketSerializer(serializers.ModelSerializer):
    usuario_detalle = UsuarioMiniSerializer(source='usuario', read_only=True)
    
    class Meta:
            model = RespuestaTicket
            fields = ['id_respuesta', 'ticket', 'usuario', 'usuario_detalle', 'contenido', 'es_nota_interna', 'mencionados', 'fecha_creacion']
        
class TicketSerializer(serializers.ModelSerializer):
    creado_por_detalle = UsuarioMiniSerializer(source='creado_por', read_only=True)
    asignado_a_detalle = UsuarioMiniSerializer(source='asignado_a', read_only=True)
    colaborador_detalle = UsuarioMiniSerializer(source='colaborador', read_only=True)
    respuestas = RespuestaTicketSerializer(many= True, read_only=True)
    imagen = serializers.ImageField(required=False, allow_null=True)
    imagen_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = '__all__'
        
        extra_kwargs={
            'asignado_a': {'required':False, 'allow_null':True},
            'colaborador': {'required':False, 'allow_null':True},
            'fecha_eliminacion': {'required':False, 'allow_null':True},
            'en_papelera': {'required':False}
        }
    
    def get_imagen_url(self, obj):
        request = self.context.get('request')
        if obj.imagen:
            if request:
                return request.build_absolute_uri(obj.imagen.url)
            return f'http://127.0.0.1:8000{obj.imagen.url}'
        return None
        
class RegistroSerializer(serializers.ModelSerializer):
    correo = serializers.EmailField(required=True)
    nombre = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    
    class Meta:
        model=Usuario
        fields = ['id_usuario', 'nombre', 'correo', 'usuario_seccion', 'password', 'rol']
        extra_kwargs = {
            'rol': {'required': False, 'default': 'cliente'},
            'usuario_seccion': {'required': False, 'allow_null': True, 'allow_blank': True}
        }
    
    def validate_email(self, value):
        if Usuario.objects.filter(correo=value).exists():
            raise serializers.ValidationError('Este correo electrónico ya está registrado.')
        return value
    
    def create(self, validated_data):
        correo = validated_data.get('correo')
        
        if not validated_data.get('usuario_seccion'):
            validated_data['usuario_seccion'] = correo

        validated_data['password'] = make_password(validated_data['password'])

        if 'rol' not in validated_data:
            validated_data['rol'] = 'cliente'
            
        return super().create(validated_data)
    
class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id_usuario', 'nombre', 'correo', 'usuario_seccion', 'rol']