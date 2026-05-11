from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Demo', '0002_demoschedulelead_alter_demoschedule_leads'),
    ]

    operations = [
        migrations.AddField(
            model_name='demoschedule',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Scheduled'),
                    ('rescheduled', 'Rescheduled'),
                ],
                default='scheduled',
                max_length=20,
            ),
        ),
    ]
