import core.models
import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('role', models.CharField(choices=[('ADMIN', 'Admin'), ('MANUFACTURER', 'Manufacturer'), ('RETAILER', 'Retailer')], default='RETAILER', max_length=20)),
                ('license_no', models.CharField(blank=True, max_length=50)),
                ('address', models.CharField(blank=True, max_length=255)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='Medicine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('generic_name', models.CharField(max_length=100)),
                ('manufacturer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medicines', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Batch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_number', models.CharField(max_length=50)),
                ('expiry_date', models.DateField()),
                ('batch_code', models.CharField(default=core.models.new_code, max_length=32, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('medicine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batches', to='core.medicine')),
            ],
        ),
        migrations.CreateModel(
            name='MedicineUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unique_hash_code', models.CharField(max_length=64, unique=True)),
                ('serial_number', models.CharField(max_length=20, unique=True)),
                ('total_pills', models.PositiveIntegerField(default=10)),
                ('sold_pills', models.PositiveIntegerField(default=0)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='units', to='core.batch')),
                ('current_owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='owned_units', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='OwnershipTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('CONFIRMED', 'Confirmed')], default='PENDING', max_length=10)),
                ('transfer_date', models.DateTimeField(auto_now_add=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('from_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_transfers', to=settings.AUTH_USER_MODEL)),
                ('to_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_transfers', to=settings.AUTH_USER_MODEL)),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfers', to='core.medicineunit')),
            ],
        ),
        migrations.CreateModel(
            name='VerificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scanned_at', models.DateTimeField(auto_now_add=True)),
                ('location', models.CharField(blank=True, max_length=100)),
                ('scan_count', models.PositiveIntegerField(default=1)),
                ('is_suspicious', models.BooleanField(default=False)),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='core.medicineunit')),
            ],
        ),
    ]
