from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('campaign', '0001_initial'),
        ('instructors', '0001_initial'),
        ('LeadManagement', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DemoSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduled_at', models.DateTimeField()),
                ('meeting_link', models.URLField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demo_schedules', to='campaign.campaign')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_demo_schedules', to=settings.AUTH_USER_MODEL)),
                ('instructor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demo_schedules', to='instructors.instructor')),
                ('leads', models.ManyToManyField(blank=True, related_name='demo_schedules', to='LeadManagement.Lead')),
            ],
            options={
                'ordering': ['-scheduled_at'],
            },
        ),
    ]
