from django.db import migrations


MOVED = {
    'medicine': 'medicines',
    'batch': 'medicines',
    'medicineunit': 'medicines',
    'ownershiptransfer': 'tracking',
    'verificationlog': 'tracking',
    'sale': 'tracking',
}


def move_content_types(apps, schema_editor, *, reverse=False):
    alias = schema_editor.connection.alias
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('core', 'User')
    LogEntry = apps.get_model('admin', 'LogEntry')
    for model_name, destination in MOVED.items():
        source, target = (destination, 'core') if reverse else ('core', destination)
        current = ContentType.objects.using(alias).filter(app_label=source, model=model_name).first()
        if current is None:
            continue
        duplicate = ContentType.objects.using(alias).filter(app_label=target, model=model_name).first()
        if duplicate is not None and duplicate.pk != current.pk:
            # A targeted/partial migrate can have already created destination
            # content types. Merge their permissions without losing grants.
            for permission in Permission.objects.using(alias).filter(content_type_id=duplicate.pk):
                canonical, _ = Permission.objects.using(alias).get_or_create(
                    content_type_id=current.pk, codename=permission.codename,
                    defaults={'name': permission.name},
                )
                for through, owner_field in (
                    (User.user_permissions.through, 'user_id'),
                    (Group.permissions.through, 'group_id'),
                ):
                    owners = through.objects.using(alias).filter(permission_id=permission.pk).values_list(owner_field, flat=True)
                    for owner_id in owners:
                        through.objects.using(alias).get_or_create(
                            **{owner_field: owner_id, 'permission_id': canonical.pk},
                        )
            LogEntry.objects.using(alias).filter(content_type_id=duplicate.pk).update(content_type_id=current.pk)
            duplicate.delete(using=alias)
        current.app_label = target
        current.save(using=alias, update_fields=['app_label'])


def forwards(apps, schema_editor):
    move_content_types(apps, schema_editor)


def backwards(apps, schema_editor):
    move_content_types(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_seal_existing_records'),
        ('medicines', '0001_adopt_existing_tables'),
        ('tracking', '0001_adopt_existing_tables'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('admin', '0003_logentry_add_action_flag_choices'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.DeleteModel(name=name) for name in (
                'OwnershipTransfer', 'VerificationLog', 'Sale',
                'MedicineUnit', 'Batch', 'Medicine',
            )],
        ),
    ]
