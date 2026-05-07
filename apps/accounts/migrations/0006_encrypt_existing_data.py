"""Step 2 of 3: encrypt existing phone/email values and populate hash fields."""
from django.db import migrations


def encrypt_existing(apps, schema_editor):
    from apps.accounts.crypto import encrypt, make_hash

    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():
        changed = False

        # phone_number: encrypt if not already a Fernet token
        if user.phone_number and not user.phone_number.startswith('gAAA'):
            raw = user.phone_number
            user.phone_number = encrypt(raw)
            user.phone_hash = make_hash(raw)
            changed = True

        # email: encrypt if not already a Fernet token
        if user.email and not user.email.startswith('gAAA'):
            raw = user.email
            user.email = encrypt(raw)
            user.email_hash = make_hash(raw)
            changed = True

        if changed:
            user.save(update_fields=['phone_number', 'phone_hash', 'email', 'email_hash'])


class Migration(migrations.Migration):
    """Step 2 of 3: populate encrypted values and hash fields."""

    dependencies = [
        ('accounts', '0005_encrypt_phone_email'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, migrations.RunPython.noop),
    ]
