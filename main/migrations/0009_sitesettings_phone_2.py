from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_blogpost_blogpostphoto'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='phone_2',
            field=models.CharField(blank=True, max_length=20, verbose_name='Второй телефон'),
        ),
    ]
