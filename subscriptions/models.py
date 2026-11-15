from django.db import models
from django.core.exceptions import ValidationError

class Hotel(models.Model):
    name = models.CharField(max_length=200)
    contact = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    def __str__(self):
        return self.name

class Installation(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.PROTECT, related_name='installations')
    identifier = models.UUIDField(unique=True)
    sync_token_hash = models.CharField(max_length=64, blank=True, editable=False)
    sync_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    last_sync_at = models.DateTimeField(null=True, editable=False)
    active_branches = models.PositiveIntegerField(null=True, blank=True)
    website = models.URLField(blank=True)
    deployment_branch = models.CharField(max_length=160, blank=True)
    def __str__(self):
        return str(self.identifier)

class License(models.Model):
    installation = models.ForeignKey(Installation, on_delete=models.PROTECT, related_name='licenses')
    serial = models.UUIDField(unique=True)
    plan = models.CharField(max_length=100)
    starts_on = models.DateField()
    ends_on = models.DateField()
    branch_limit = models.PositiveIntegerField()
    warning_days = models.PositiveIntegerField(default=14)
    grace_days = models.PositiveIntegerField(default=7)
    activated = models.BooleanField(default=False)
    def clean(self):
        if self.starts_on and self.ends_on and self.starts_on > self.ends_on:
            raise ValidationError({'ends_on': 'تاريخ الانتهاء يجب أن يلي تاريخ البداية.'})
        if self.branch_limit == 0:
            raise ValidationError({'branch_limit': 'حد الفروع يجب أن يكون واحدًا على الأقل.'})
    def __str__(self):
        return str(self.serial)


