from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Thread


@receiver(post_delete, sender=Thread)
def delete_thread_cover(sender, instance, **kwargs):
    if instance.cover_image:
        storage, name = instance.cover_image.storage, instance.cover_image.name
        transaction.on_commit(lambda: storage.delete(name))
