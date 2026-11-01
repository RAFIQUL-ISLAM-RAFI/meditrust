from django.db import migrations


def seal_existing(apps, schema_editor):
    from core.utils import batch_signature, unit_signature
    Batch = apps.get_model('core', 'Batch')
    Unit = apps.get_model('core', 'MedicineUnit')
    alias = schema_editor.connection.alias
    for batch in Batch.objects.using(alias).select_related('medicine').filter(integrity_signature='').iterator():
        Batch.objects.using(alias).filter(pk=batch.pk).update(integrity_signature=batch_signature(batch))
    for unit in Unit.objects.using(alias).select_related('batch__medicine').filter(integrity_signature='').iterator():
        Unit.objects.using(alias).filter(pk=unit.pk).update(integrity_signature=unit_signature(unit))


class Migration(migrations.Migration):
    dependencies = [('core', '0002_alter_user_managers_batch_integrity_signature_and_more')]
    operations = [migrations.RunPython(seal_existing, migrations.RunPython.noop)]
