from django.db import models
from django.contrib.auth.models import User

TIPOS_LOCAL = [
    ("local", "Local"),
    ("boleteria", "Boletería"),
    ("pescaderia", "Pescadería"),
    ("lote6", "Lote 6"),
    ("kiosco", "Kiosco"),
]

TIPOS_MENSUALES = ("boleteria", "pescaderia")

ROLES = [
    ("caja", "Caja"),
    ("tesoreria", "Tesorería"),
    ("administrador", "Administrador"),
]

ACCIONES = [
    ("crear", "Crear pago"),
    ("abonar", "Abonar"),
]


class Perfil(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=ROLES, default="caja")

    def __str__(self):
        return f"{self.user.username} ({self.get_rol_display()})"


class Local(models.Model):
    numero = models.CharField(max_length=10, unique=True)
    tipo = models.CharField(max_length=20, choices=TIPOS_LOCAL)
    ocupado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.numero} - {self.get_tipo_display()}"


class Pago(models.Model):
    local = models.ForeignKey(Local, on_delete=models.PROTECT, related_name="pagos")
    fecha = models.DateField()
    mes = models.CharField(max_length=20, blank=True)
    empresario = models.CharField(max_length=150, blank=True)
    rut = models.CharField(max_length=15, blank=True)
    descripcion = models.CharField(max_length=255, blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateField(null=True, blank=True)
    folio = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return f"{self.local.numero} - {self.folio}"


class Historial(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name="historial")
    accion = models.CharField(max_length=20, choices=ACCIONES)
    tipo = models.CharField(max_length=20)
    folio = models.CharField(max_length=30)
    local_numero = models.CharField(max_length=10)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fecha_hora:%Y-%m-%d %H:%M} - {self.usuario.username} - {self.get_accion_display()} - {self.folio}"


class LoginLog(models.Model):
    ACCIONES_LOGIN = [
        ("login", "Inicio de sesión"),
        ("logout", "Cierre de sesión"),
    ]
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name="login_logs")
    accion = models.CharField(max_length=10, choices=ACCIONES_LOGIN)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fecha_hora:%Y-%m-%d %H:%M} - {self.usuario.username} - {self.get_accion_display()}"
