# Generated manually for version history tracking

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('pocs', '0002_auto_20250326_1605'),
    ]

    operations = [
        migrations.AddField(
            model_name='proofofconcept',
            name='previous_version',
            field=models.ForeignKey(
                blank=True,
                help_text='Previous version of this PoC (for regeneration history)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='next_versions',
                to='pocs.proofofconcept'
            ),
        ),
    ]