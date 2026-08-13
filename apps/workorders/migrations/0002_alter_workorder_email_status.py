from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workorders", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workorder",
            name="email_status",
            field=models.CharField(
                choices=[
                    ("NOT_SENT", "未发送"),
                    ("SENDING", "发送中"),
                    ("FAILED", "失败"),
                    ("SENT", "已发送"),
                    ("OUTCOME_UNKNOWN", "发送结果未知"),
                ],
                default="NOT_SENT",
                max_length=24,
            ),
        ),
    ]
