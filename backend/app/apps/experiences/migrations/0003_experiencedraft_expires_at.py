from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("experiences", "0002_experiencedraft_published_at_experiencedraft_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="experiencedraft",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
