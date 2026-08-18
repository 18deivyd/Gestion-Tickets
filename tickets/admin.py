from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserADmin
from .models import Usuario, Ticket

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display=('id_usuario', 'usuario_seccion','nombre','rol','activo')
    list_filter=('rol','is_staff')
    search_fields=('usuario_seccion', 'nombre')
    
    def save_model(self, request, obj, form, change):
        if not obj.password.startswith('pbkdf2_sha256$') and not obj.password.startswith('argon2'):
            obj.set_password(obj.password)
        super().save_model(request, obj, form, change)
    
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display=('id_ticket','asunto','estado','prioridad','creado_por','asignado_a','fecha_creacion')
    list_filter=('estado','prioridad')
    search_fields=('asunto','descripcion')
