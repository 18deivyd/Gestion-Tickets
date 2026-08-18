# 🎫 TicketBridge

**TicketBridge** es un sistema integral de gestión de soporte técnico e incidencias IT (Helpdesk) construido con Django y Next.js. La plataforma permite canalizar solicitudes a través de correo electrónico (vía IMAP/SMTP) e interfaz web, permitiendo a los agentes responder, categorizar, asignar prioridades y dejar notas internas de forma eficiente.

---

## 🚀 Características Principales

- **📧 Sincronización de Correo Electrónico:** 
  - Conversión automática de correos entrantes (IMAP) en tickets.
  - Notificaciones y respuestas salientes enviadas por SMTP al usuario final.
- **👥 Mesa de Ayuda Multiagente:**
  - Control de acceso y permisos por roles (Administrador, Agente, Cliente).
  - Flujo de estados: *Abierto, En Proceso, Pendiente, Resuelto, Cerrado*.
  - Asignación de prioridad, departamento y agente encargado.
- **💬 Comunicación y Auditoría:**
  - Historial de respuestas públicas y notas internas visibles solo para el equipo.
  - Soporte para archivos adjuntos en tickets.
- **💻 Arquitectura Desacoplada (Decoupled):**
  - Backend robusto REST API construido con Django REST Framework.
  - Frontend interactivo e intuitivo desarrollado en Next.js/React.

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
| :--- | :--- |
| **Backend** | Python 3.12+, Django 5.0, Django REST Framework |
| **Frontend** | React, Next.js 14, Tailwind CSS |
| **Base de Datos** | MySQL 8.0+ |
| **Integraciones** | IMAP / SMTP (Email Sync), `python-dotenv` |

---

## 📁 Estructura del Proyecto

```text
TicketBridge/
├── project/              # Configuración principal de Django (settings.py, urls.py, wsgi.py)
├── tickets/              # Aplicación core de Django (modelos, vistas, serializadores, vistas API)
├── cliente-tickets/      # Frontend de la aplicación (Next.js / React)
├── .env                  # Variables de entorno (No se sube al repositorio)
├── .gitignore            # Archivos e historial ignorados por Git
├── manage.py             # Script de administración de Django
└── README.md             # Documentación principal
