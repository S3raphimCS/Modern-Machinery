"""Сериализаторы модуля компании."""

from rest_framework import serializers

from apps.company.models import Branch, ContactPoint, Department, Employee


class ContactPointSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    display_value = serializers.CharField(read_only=True)

    class Meta:
        model = ContactPoint
        fields = ["kind", "kind_display", "value", "extension", "label", "display_value"]


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name"]


class EmployeeSerializer(serializers.ModelSerializer):
    department = serializers.CharField(source="department.name", read_only=True)
    contacts = ContactPointSerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "full_name", "position", "department", "email", "photo", "contacts"]


class BranchSerializer(serializers.ModelSerializer):
    contacts = ContactPointSerializer(many=True, read_only=True)
    employees = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "slug",
            "city",
            "address",
            "postcode",
            "latitude",
            "longitude",
            "timezone",
            "work_hours",
            "description",
            "contacts",
            "employees",
        ]

    def get_employees(self, obj: Branch) -> list[dict]:
        employees = obj.employees.filter(is_published=True).select_related("department")
        return EmployeeSerializer(employees, many=True, context=self.context).data
