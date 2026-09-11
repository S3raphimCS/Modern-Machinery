"""Фабрики пользователей для тестов."""

import factory
from django.contrib.auth import get_user_model


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@modernmachinery.ru")
    first_name = "Иван"
    last_name = "Петров"
    is_staff = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):  # noqa: N805
        if not create:
            return
        obj.set_password(extracted or "test-password")
        obj.save(update_fields=["password"])


class StaffUserFactory(UserFactory):
    is_staff = True
    is_superuser = True
