# Generated manually for schema repair

from django.db import migrations, models
import django.core.validators

class Migration(migrations.Migration):

    dependencies = [
        ('pocs', '0001_initial'),
    ]

    operations = [
        # First, try to drop the columns if they exist (this will silently fail if they don't exist)
        migrations.RunSQL(
            "ALTER TABLE pocs_proofofconcept DROP COLUMN IF EXISTS effectiveness_score;",
            reverse_sql=migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            "ALTER TABLE pocs_proofofconcept DROP COLUMN IF EXISTS feedback_categories;",
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Now add the columns
        migrations.RunSQL(
            """
            ALTER TABLE pocs_proofofconcept 
            ADD COLUMN effectiveness_score integer NULL;
            """,
            reverse_sql="ALTER TABLE pocs_proofofconcept DROP COLUMN effectiveness_score;"
        ),
        migrations.RunSQL(
            """
            ALTER TABLE pocs_proofofconcept 
            ADD COLUMN feedback_categories text NULL;
            """,
            reverse_sql="ALTER TABLE pocs_proofofconcept DROP COLUMN feedback_categories;"
        ),
    ]