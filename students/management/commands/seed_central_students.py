from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from students.models import Student
from finance.models import StudentAccount
from audit.models import AuditEntry

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds Central University Database with Day Scholar students and updates residency designations."

    def handle(self, *args, **options):
        self.stdout.write("Initializing Central University Student Database...")

        with transaction.atomic():
            # 1. Update existing students
            for s in Student.objects.all():
                if s.current_bed:
                    s.student_type = 'HOSTEL'
                else:
                    s.student_type = 'DAY_SCHOLAR'
                s.save(update_fields=['student_type'])

            self.stdout.write("  [OK] Updated residency status for existing students.")

            # 2. Add realistic Day Scholar students
            day_scholars_data = [
                ('12313714', 'Aarav', 'Sharma', 'Male', 'B.Tech Computer Science', 'Engineering', '2nd Year', 2025),
                ('12313715', 'Rohan', 'Gupta', 'Male', 'B.Tech Mechanical Eng', 'Engineering', '3rd Year', 2024),
                ('12313716', 'Simran', 'Kaur', 'Female', 'BBA Management', 'Business School', '1st Year', 2026),
                ('12313717', 'Neha', 'Patel', 'Female', 'B.Tech Information Tech', 'Engineering', '2nd Year', 2025),
                ('12313718', 'Karan', 'Verma', 'Male', 'MBA Finance & Tech', 'Business School', '1st Year', 2026),
                ('12313719', 'Tanvi', 'Joshi', 'Female', 'B.Tech Artificial Intelligence', 'Engineering', '2nd Year', 2025),
            ]

            demo_password = 'HostelX@2026'

            created_count = 0
            for reg_no, first, last, gender, course, dept, year, adm_year in day_scholars_data:
                # Create user with username = reg_no (e.g. 12313714)
                u, u_created = User.objects.get_or_create(
                    username=reg_no,
                    defaults={
                        'email': f"{reg_no}@student.university.edu",
                        'first_name': first,
                        'last_name': last,
                        'role': User.Role.STUDENT,
                        'phone_number': f"+91-98765{reg_no[-5:]}"
                    }
                )
                if u_created or not u.has_usable_password():
                    u.set_password(demo_password)
                    u.save()

                # Create Student Profile as Day Scholar
                stu, s_created = Student.objects.get_or_create(
                    user=u,
                    defaults={
                        'student_id': f"STU_{reg_no}",
                        'registration_number': reg_no,
                        'full_name': f"{first} {last}",
                        'email': u.email,
                        'mobile_number': u.phone_number,
                        'gender': gender,
                        'student_type': 'DAY_SCHOLAR',
                        'course': course,
                        'department': dept,
                        'academic_year': year,
                        'admission_year': adm_year,
                        'fee_status': 'PAID',
                        'disciplinary_status': 'CLEAN',
                        'account_status': 'ACTIVE',
                        'current_hostel': None,
                        'current_room': None,
                        'current_bed': None,
                    }
                )

                StudentAccount.objects.get_or_create(
                    student=stu,
                    defaults={'balance': Decimal('0.00'), 'outstanding_due': Decimal('0.00')}
                )

                if s_created:
                    created_count += 1
                    AuditEntry.objects.create(
                        actor=u,
                        action='CENTRAL_DB_ENROLLMENT',
                        entity_type='Student',
                        entity_id=str(stu.id),
                        description=f"Enrolled Day Scholar {stu.full_name} ({stu.registration_number}) into Central University Database."
                    )

            self.stdout.write(self.style.SUCCESS(f"  [SUCCESS] Central University Database updated! Added {created_count} Day Scholar students (e.g. 12313714)."))
