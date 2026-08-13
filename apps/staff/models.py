from django.db import models
from django.db.models import Q


class Employee(models.Model):
    employee_id = models.CharField(max_length=64, primary_key=True)
    employee_name = models.CharField(max_length=120)
    email = models.EmailField()
    production_line = models.CharField(max_length=120, blank=True, default="")
    skills_json = models.JSONField(default=list)
    current_load = models.DecimalField(max_digits=5, decimal_places=4)
    on_duty = models.BooleanField(default=True)
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(current_load__gte=0) & Q(current_load__lte=1),
                name="employee_load_between_0_and_1",
            )
        ]
        indexes = [models.Index(fields=["available", "on_duty", "current_load"])]

    def __str__(self):
        return f"{self.employee_id} {self.employee_name}"
