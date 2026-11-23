# Parqueadero Unimonserrate — Sistema Inteligente de Control de Acceso y Movilidad IoT

Proyecto desarrollado para la **Fundación Universitaria Monserrate** (Ingeniería de Software II).

## Características Principales
- **Control de Acceso Basado en Roles (RBAC):** Autenticación diferenciada para Comunidad Universitaria (Estudiantes/Docentes), Portería en Turno (con código de turno `8844`) y Dirección Administrativa (con PIN maestro `2026`).
- **Tokens QR Dinámicos (JWT 60s):** Prevención de suplantación o captura de pantalla mediante expiración automática cada 60 segundos.
- **BiciParqueadero Institucional ($0):** Acceso gratuito automático para bicicletas registradas por estudiantes, docentes y administrativos.
- **Integración IoT y Cámaras LPR:** Sincronización en tiempo real de 30 celdas (Carros, Motos y Bicicletas), control de talanquera LPR y protección mediante llave maestra de hardware.
- **Gestión de Visitantes y Tarifas Parametrizables:** Generación de tickets QR para invitados, integración con WhatsApp y auditoría histórica de tarifas.

## Ejecución Local
1. Activar el entorno virtual:
   ```powershell
   .\venv\Scripts\activate