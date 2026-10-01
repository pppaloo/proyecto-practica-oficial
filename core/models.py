from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User

TIPOS_LOCAL = [
    ("local", "Local"),
    ("boleteria", "Boletería"),
    ("pescaderia", "Pescadería"),
    ("lote6", "Lote 6"),
    ("kiosco", "Kiosco"),
    ("centro_comercial", "Centro Comercial"),
]

ROLES = [
    ("caja", "Caja"),
    ("tesoreria", "Tesorería"),
    ("administrador", "Administrador"),
]

ACCIONES = [
    ("crear", "Crear pago"),
    ("abonar", "Abonar"),
    ("editar", "Editar pago"),
    ("eliminar", "Eliminar pago"),
    ("generar", "Generar deuda"),
]


class Perfil(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=ROLES, default="caja")

    def __str__(self):
        return f"{self.user.username} ({self.get_rol_display()})"


class Local(models.Model):
    numero = models.CharField(max_length=10, unique=True)
    tipo = models.CharField(max_length=20, choices=TIPOS_LOCAL)
    cantidad_utm = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
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
    tipo_deuda = models.CharField(max_length=100, blank=True)
    domicilio = models.CharField(max_length=200, blank=True)
    fono = models.CharField(max_length=30, blank=True)
    correo = models.CharField(max_length=150, blank=True)
    periodo = models.CharField(max_length=50, blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateField(null=True, blank=True)
    folio = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return f"{self.local.numero} - {self.folio}"


class PagoDiario(models.Model):
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name="detalles_diarios")
    fecha = models.DateField()
    dia = models.CharField(max_length=15, blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    folio = models.CharField(max_length=30, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.pago.folio} {self.fecha} - {self.valor}"


class ValorUTM(models.Model):
    anio = models.IntegerField()
    mes = models.IntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    asignado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("anio", "mes")

    def __str__(self):
        return f"UTM {self.mes}/{self.anio} = {self.valor}"


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
