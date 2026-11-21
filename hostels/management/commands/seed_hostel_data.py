import random
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from hostels.models import University, Hostel, Warden, Announcement
from rooms.models import RoomCategory, Room, Bed, RoomPricing
from students.models import Student
from allocations.models import BedAllocation
from exchanges.models import PolicyRule
from finance.models import StudentAccount
from facilities.models import Facility
from mess.models import MessMenu, MessRegistration
from laundry.models import LaundryService, LaundryRequest
from maintenance.models import MaintenanceRequest

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with comprehensive university hostel data (Hostels, Rooms, Beds, Students, Wardens, Mess, Laundry, Pricing, etc.)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting HostelX comprehensive database seeding..."))

        with transaction.atomic():
            # 1. Policy Rule
            policy, _ = PolicyRule.objects.get_or_create(
                code='DEFAULT',
                defaults={
                    'name': 'Standard University Hostel Exchange Policy',
                    'is_enabled': True,
                    'max_cycle_length': 5,
                    'allow_cross_hostel': True,
                    'allow_cross_category': True,
                    'allow_cross_academic_year': True,
                    'allow_cross_course': True,
                    'processing_fee': Decimal('200.00'),
                    'proposal_expiry_hours': 72,
                    'cooling_off_days': 30,
                    'max_exchanges_per_year': 2,
                }
            )
            self.stdout.write("  [OK] Policy rules verified.")

            # 2. University
            university, _ = University.objects.get_or_create(
                code='ANIT',
                defaults={
                    'name': 'Apex National Institute of Technology',
                    'address': 'Knowledge City, Tech Corridor, Bangalore 560100',
                    'contact_email': 'hostels@anit.edu.in',
                    'contact_phone': '+91-80-28001000',
                }
            )
            self.stdout.write("  [OK] University created/verified.")

            # 3. Hostels
            hostels_data = [
                ('H001', 'Boys Hostel A', 'Male', 'North Campus, Quad 1'),
                ('H002', 'Boys Hostel B', 'Male', 'North Campus, Quad 2'),
                ('H003', 'Girls Hostel A', 'Female', 'South Campus, Block 1'),
                ('H004', 'Girls Hostel B', 'Female', 'South Campus, Block 2'),
            ]

            hostels = {}
            for code, name, gender, address in hostels_data:
                h, _ = Hostel.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'gender': gender,
                        'university': university,
                        'address': address,
                        'total_floors': 4,
                    }
                )
                hostels[code] = h
            self.stdout.write(f"  [OK] {len(hostels)} Hostels verified.")

            # 4. Room Categories
            categories_data = [
                ('AC Single Occupancy', True, 1, 'Premium single room with air conditioning and study desk.'),
                ('AC Double Occupancy', True, 2, 'Twin sharing room with air conditioning and ensuite storage.'),
                ('AC Triple Occupancy', True, 3, 'Triple occupancy room with split AC and individual wardrobes.'),
                ('AC Four Occupancy', True, 4, 'Spacious four-student dorm suite with inverter AC.'),
                ('Non-AC Triple Occupancy', False, 3, 'Well-ventilated three-bed room with ceiling fans.'),
                ('Non-AC Four Occupancy', False, 4, 'Standard economical four-student dormitory room.'),
            ]

            categories = {}
            for name, is_ac, capacity, desc in categories_data:
                cat, _ = RoomCategory.objects.get_or_create(
                    name=name,
                    defaults={'is_ac': is_ac, 'capacity': capacity, 'description': desc}
                )
                categories[name] = cat
            self.stdout.write(f"  [OK] {len(categories)} Room Categories verified.")

            # 5. Room Pricing
            pricing_map = {
                'AC Single Occupancy': Decimal('96000.00'),
                'AC Double Occupancy': Decimal('72000.00'),
                'AC Triple Occupancy': Decimal('60000.00'),
                'AC Four Occupancy': Decimal('48000.00'),
                'Non-AC Triple Occupancy': Decimal('42000.00'),
                'Non-AC Four Occupancy': Decimal('36000.00'),
            }

            for h in hostels.values():
                for cat_name, price in pricing_map.items():
                    RoomPricing.objects.get_or_create(
                        hostel=h,
                        category=categories[cat_name],
                        academic_year='2026-2027',
                        defaults={'annual_fee': price, 'is_active': True}
                    )
            self.stdout.write("  [OK] Room Pricing structures verified.")

            # 6. Admin, Wardens, Chief Warden, Dean Accounts
            demo_password = 'HostelX@2026'

            # Superuser / Admin
            admin_user, created = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@anit.edu.in',
                    'first_name': 'University',
                    'last_name': 'Administrator',
                    'role': User.Role.ADMIN,
                    'is_staff': True,
                    'is_superuser': True,
                }
            )
            if created:
                admin_user.set_password(demo_password)
                admin_user.save()

            # Chief Warden
            chief_user, created = User.objects.get_or_create(
                username='chief_warden',
                defaults={
                    'email': 'chiefwarden@anit.edu.in',
                    'first_name': 'Dr. Rajesh',
                    'last_name': 'Sharma',
                    'role': User.Role.CHIEF_WARDEN,
                    'is_staff': True,
                }
            )
            if created:
                chief_user.set_password(demo_password)
                chief_user.save()
            Warden.objects.get_or_create(
                user=chief_user,
                defaults={'is_chief': True, 'office_room': 'Central Admin #104', 'contact_number': '+91-9876543210'}
            )

            # Dean of Student Welfare
            dean_user, created = User.objects.get_or_create(
                username='dean',
                defaults={
                    'email': 'dean.sw@anit.edu.in',
                    'first_name': 'Prof. Meenakshi',
                    'last_name': 'Sundaram',
                    'role': User.Role.DEAN,
                    'is_staff': True,
                }
            )
            if created:
                dean_user.set_password(demo_password)
                dean_user.save()

            # 4 Hostel Wardens
            warden_profiles = [
                ('warden_ha', 'Dr. Suresh', 'Verma', 'H001', 'Boys Hostel A Office', '+91-9876500001'),
                ('warden_hb', 'Dr. Anil', 'Kapoor', 'H002', 'Boys Hostel B Office', '+91-9876500002'),
                ('warden_ga', 'Dr. Sunita', 'Deshmukh', 'H003', 'Girls Hostel A Office', '+91-9876500003'),
                ('warden_gb', 'Dr. Kavita', 'Nair', 'H004', 'Girls Hostel B Office', '+91-9876500004'),
            ]

            for uname, fname, lname, hcode, office, phone in warden_profiles:
                w_user, cr = User.objects.get_or_create(
                    username=uname,
                    defaults={
                        'email': f"{uname}@anit.edu.in",
                        'first_name': fname,
                        'last_name': lname,
                        'role': User.Role.WARDEN,
                        'is_staff': True,
                    }
                )
                if cr:
                    w_user.set_password(demo_password)
                    w_user.save()
                Warden.objects.get_or_create(
                    user=w_user,
                    defaults={'hostel': hostels[hcode], 'is_chief': False, 'office_room': office, 'contact_number': phone}
                )
            self.stdout.write("  [OK] Administrative and Warden accounts ready.")

            # 7. Rooms and Beds Creation
            # 30 rooms per hostel, 87 beds each = 120 rooms, 348 beds across 4 hostels.
            room_plan = [
                # Floor 1 (Rooms 101-108)
                ('101', 'AC Single Occupancy', 1),
                ('102', 'AC Double Occupancy', 1),
                ('103', 'AC Double Occupancy', 1),
                ('104', 'AC Triple Occupancy', 1),
                ('105', 'AC Triple Occupancy', 1),
                ('106', 'AC Four Occupancy', 1),
                ('107', 'Non-AC Triple Occupancy', 1),
                ('108', 'Non-AC Four Occupancy', 1),
                # Floor 2 (Rooms 201-208)
                ('201', 'AC Single Occupancy', 2),
                ('202', 'AC Double Occupancy', 2),
                ('203', 'AC Double Occupancy', 2),
                ('204', 'AC Triple Occupancy', 2),
                ('205', 'AC Triple Occupancy', 2),
                ('206', 'AC Four Occupancy', 2),
                ('207', 'Non-AC Triple Occupancy', 2),
                ('208', 'Non-AC Four Occupancy', 2),
                # Floor 3 (Rooms 301-307)
                ('301', 'AC Single Occupancy', 3),
                ('302', 'AC Double Occupancy', 3),
                ('303', 'AC Double Occupancy', 3),
                ('304', 'AC Triple Occupancy', 3),
                ('305', 'AC Triple Occupancy', 3),
                ('306', 'AC Four Occupancy', 3),
                ('307', 'Non-AC Triple Occupancy', 3),
                # Floor 4 (Rooms 401-407)
                ('401', 'AC Four Occupancy', 4),
                ('402', 'AC Four Occupancy', 4),
                ('403', 'AC Triple Occupancy', 4),
                ('404', 'Non-AC Triple Occupancy', 4),
                ('405', 'Non-AC Triple Occupancy', 4),
                ('406', 'Non-AC Four Occupancy', 4),
                ('407', 'Non-AC Four Occupancy', 4),
            ]

            male_beds = []
            female_beds = []

            for hcode, hostel in hostels.items():
                for room_no, cat_name, floor in room_plan:
                    cat = categories[cat_name]
                    room, _ = Room.objects.get_or_create(
                        hostel=hostel,
                        room_number=room_no,
                        defaults={'floor': floor, 'category': cat, 'is_active': True}
                    )
                    # Create beds for room
                    for b_idx in range(1, cat.capacity + 1):
                        bed_id = f"B{b_idx}"
                        bed, _ = Bed.objects.get_or_create(
                            room=room,
                            bed_identifier=bed_id,
                            defaults={'status': 'VACANT'}
                        )
                        if hostel.gender == 'Male':
                            male_beds.append(bed)
                        else:
                            female_beds.append(bed)

            self.stdout.write(f"  [OK] Created rooms and beds: {len(male_beds)} male beds, {len(female_beds)} female beds. Total: {len(male_beds)+len(female_beds)} beds.")

            # 8. Students Creation and Allocations
            # 160 male students, 160 female students.
            # Leaving ~14 vacant beds in boys hostels and ~14 vacant beds in girls hostels for swap flexibility!
            courses = [
                ('B.Tech Computer Science', 'Computer Science & Eng'),
                ('B.Tech Electronics & Comm', 'Electronics & Comm Eng'),
                ('B.Tech Mechanical Eng', 'Mechanical Eng'),
                ('B.Tech Civil Eng', 'Civil Eng'),
                ('B.Tech Artificial Intelligence', 'Computer Science & Eng'),
                ('MBA Finance & Tech', 'Management Studies'),
                ('M.Tech Data Science', 'Computer Science & Eng'),
            ]
            academic_years = ['1st Year', '2nd Year', '3rd Year', '4th Year']

            male_names = [
                ("Rahul", "Sharma"), ("Amit", "Verma"), ("Vikram", "Rao"), ("Rohit", "Patel"),
                ("Aditya", "Singh"), ("Manish", "Gupta"), ("Siddharth", "Reddy"), ("Karthik", "Menon"),
                ("Varun", "Joshi"), ("Naveen", "Kumar"), ("Deepak", "Choudhury"), ("Gaurav", "Mishra"),
                ("Ayush", "Saxena"), ("Pranav", "Nair"), ("Harsh", "Bansal"), ("Arjun", "Malhotra"),
                ("Rishabh", "Mehta"), ("Abhishek", "Pandey"), ("Kunal", "Sen"), ("Yash", "Aggarwal"),
                ("Tushar", "Deshmukh"), ("Ankit", "Trivedi"), ("Sameer", "Bhatia"), ("Rohan", "Kapoor"),
                ("Akash", "Dubey"), ("Nikhil", "Pillai"), ("Dev", "Nambiar"), ("Mohit", "Yadav"),
                ("Saurabh", "Dutta"), ("Chetan", "Kulkarni")
            ]

            female_names = [
                ("Priya", "Nair"), ("Sneha", "Kulkarni"), ("Ananya", "Sen"), ("Pooja", "Menon"),
                ("Divya", "Sharma"), ("Neha", "Reddy"), ("Riya", "Chatterjee"), ("Tanvi", "Joshi"),
                ("Aastha", "Verma"), ("Kritika", "Gupta"), ("Swati", "Mishra"), ("Isha", "Bansal"),
                ("Megha", "Rao"), ("Shruti", "Patel"), ("Bhavna", "Singh"), ("Simran", "Kaur"),
                ("Nandini", "Pillai"), ("Roshni", "Kapoor"), ("Shreya", "Deshmukh"), ("Pallavi", "Dubey"),
                ("Anjali", "Saxena"), ("Vandana", "Yadav"), ("Radhika", "Mehta"), ("Sanya", "Trivedi"),
                ("Garima", "Bhatia"), ("Komal", "Dutta"), ("Payal", "Malhotra"), ("Juhi", "Choudhury"),
                ("Aditi", "Pandey"), ("Ritu", "Kumar")
            ]

            # Specific demo students with predictable usernames
            key_demo_students = [
                # Male demo accounts
                ('student_rahul', 'Rahul', 'Sharma', 'Male', 'H001', '101', 'B1', 'PAID', 'CLEAN'),
                ('student_amit', 'Amit', 'Verma', 'Male', 'H001', '102', 'B1', 'PAID', 'CLEAN'),
                ('student_vikram', 'Vikram', 'Rao', 'Male', 'H002', '101', 'B1', 'PAID', 'CLEAN'),
                ('student_rohit', 'Rohit', 'Patel', 'Male', 'H002', '102', 'B1', 'PAID', 'CLEAN'),
                ('student_unpaid', 'Aditya', 'Singh', 'Male', 'H001', '103', 'B1', 'UNPAID', 'CLEAN'),
                ('student_hold', 'Manish', 'Gupta', 'Male', 'H001', '104', 'B1', 'PAID', 'HOLD'),
                # Female demo accounts
                ('student_priya', 'Priya', 'Nair', 'Female', 'H003', '101', 'B1', 'PAID', 'CLEAN'),
                ('student_sneha', 'Sneha', 'Kulkarni', 'Female', 'H003', '102', 'B1', 'PAID', 'CLEAN'),
                ('student_ananya', 'Ananya', 'Sen', 'Female', 'H004', '101', 'B1', 'PAID', 'CLEAN'),
                ('student_pooja', 'Pooja', 'Menon', 'Female', 'H004', '102', 'B1', 'PAID', 'CLEAN'),
            ]

            allocated_beds = set()

            # Allocate key demo students first
            demo_student_objs = []
            for username, first, last, gender, hcode, rno, bno, fee_st, disc_st in key_demo_students:
                u, cr = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': f"{username}@student.anit.edu.in",
                        'first_name': first,
                        'last_name': last,
                        'role': User.Role.STUDENT,
                    }
                )
                if cr:
                    u.set_password(demo_password)
                    u.save()

                target_hostel = hostels[hcode]
                target_room = Room.objects.get(hostel=target_hostel, room_number=rno)
                target_bed = Bed.objects.get(room=target_room, bed_identifier=bno)

                stu, _ = Student.objects.get_or_create(
                    user=u,
                    defaults={
                        'student_id': f"STU2026_{username.upper()}",
                        'registration_number': f"REG2026_{username.upper()}",
                        'full_name': f"{first} {last}",
                        'email': u.email,
                        'mobile_number': '+91-9811223344',
                        'gender': gender,
                        'course': 'B.Tech Computer Science',
                        'department': 'Computer Science & Eng',
                        'academic_year': '3rd Year',
                        'admission_year': 2024,
                        'current_hostel': target_hostel,
                        'current_room': target_room,
                        'current_bed': target_bed,
                        'fee_status': fee_st,
                        'disciplinary_status': disc_st,
                        'account_status': 'ACTIVE',
                    }
                )
                # Link bed
                target_bed.status = 'OCCUPIED'
                target_bed.save()
                allocated_beds.add(target_bed.id)

                # Allocation record
                BedAllocation.objects.get_or_create(
                    student=stu,
                    bed=target_bed,
                    academic_year='2026-2027',
                    defaults={'is_active': True, 'remarks': 'Initial session allotment'}
                )

                # Student Financial Account
                StudentAccount.objects.get_or_create(
                    student=stu,
                    defaults={'balance': Decimal('500.00'), 'outstanding_due': Decimal('0.00')}
                )

                # Mess Registration
                MessRegistration.objects.get_or_create(
                    student=stu,
                    defaults={'hostel': target_hostel, 'dietary_preference': 'VEG', 'is_active': True}
                )
                demo_student_objs.append(stu)

            self.stdout.write(f"  [OK] Seeded {len(demo_student_objs)} key demo student accounts.")

            # Seed remaining male students (target: 155 males)
            male_available_beds = [b for b in male_beds if b.id not in allocated_beds]
            random.seed(42)

            for i in range(1, 155):
                uname = f"stu_m_{i:03d}"
                first, last = male_names[i % len(male_names)]
                course_name, dept_name = courses[i % len(courses)]
                acad_year = academic_years[i % len(academic_years)]

                u, cr = User.objects.get_or_create(
                    username=uname,
                    defaults={
                        'email': f"{uname}@student.anit.edu.in",
                        'first_name': first,
                        'last_name': f"{last} {i}",
                        'role': User.Role.STUDENT,
                    }
                )
                if cr:
                    u.set_password(demo_password)
                    u.save()

                bed = male_available_beds[i - 1]
                hostel = bed.room.hostel
                room = bed.room

                stu, _ = Student.objects.get_or_create(
                    user=u,
                    defaults={
                        'student_id': f"STU2026M{i:03d}",
                        'registration_number': f"REG2026M{i:03d}",
                        'full_name': f"{first} {last} {i}",
                        'email': u.email,
                        'mobile_number': f"+91-98{i:08d}",
                        'gender': 'Male',
                        'course': course_name,
                        'department': dept_name,
                        'academic_year': acad_year,
                        'admission_year': 2026 - int(acad_year[0]),
                        'current_hostel': hostel,
                        'current_room': room,
                        'current_bed': bed,
                        'fee_status': 'PAID',
                        'disciplinary_status': 'CLEAN',
                        'account_status': 'ACTIVE',
                    }
                )
                bed.status = 'OCCUPIED'
                bed.save()
                allocated_beds.add(bed.id)

                BedAllocation.objects.get_or_create(
                    student=stu,
                    bed=bed,
                    academic_year='2026-2027',
                    defaults={'is_active': True, 'remarks': 'Academic year 2026 allotment'}
                )
                StudentAccount.objects.get_or_create(
                    student=stu,
                    defaults={'balance': Decimal('0.00'), 'outstanding_due': Decimal('0.00')}
                )
                MessRegistration.objects.get_or_create(
                    student=stu,
                    defaults={'hostel': hostel, 'dietary_preference': 'VEG' if i % 2 == 0 else 'NON_VEG', 'is_active': True}
                )

            # Seed remaining female students (target: 155 females)
            female_available_beds = [b for b in female_beds if b.id not in allocated_beds]

            for i in range(1, 155):
                uname = f"stu_f_{i:03d}"
                first, last = female_names[i % len(female_names)]
                course_name, dept_name = courses[i % len(courses)]
                acad_year = academic_years[i % len(academic_years)]

                u, cr = User.objects.get_or_create(
                    username=uname,
                    defaults={
                        'email': f"{uname}@student.anit.edu.in",
                        'first_name': first,
                        'last_name': f"{last} {i}",
                        'role': User.Role.STUDENT,
                    }
                )
                if cr:
                    u.set_password(demo_password)
                    u.save()

                bed = female_available_beds[i - 1]
                hostel = bed.room.hostel
                room = bed.room

                stu, _ = Student.objects.get_or_create(
                    user=u,
                    defaults={
                        'student_id': f"STU2026F{i:03d}",
                        'registration_number': f"REG2026F{i:03d}",
                        'full_name': f"{first} {last} {i}",
                        'email': u.email,
                        'mobile_number': f"+91-97{i:08d}",
                        'gender': 'Female',
                        'course': course_name,
                        'department': dept_name,
                        'academic_year': acad_year,
                        'admission_year': 2026 - int(acad_year[0]),
                        'current_hostel': hostel,
                        'current_room': room,
                        'current_bed': bed,
                        'fee_status': 'PAID',
                        'disciplinary_status': 'CLEAN',
                        'account_status': 'ACTIVE',
                    }
                )
                bed.status = 'OCCUPIED'
                bed.save()
                allocated_beds.add(bed.id)

                BedAllocation.objects.get_or_create(
                    student=stu,
                    bed=bed,
                    academic_year='2026-2027',
                    defaults={'is_active': True, 'remarks': 'Academic year 2026 allotment'}
                )
                StudentAccount.objects.get_or_create(
                    student=stu,
                    defaults={'balance': Decimal('0.00'), 'outstanding_due': Decimal('0.00')}
                )
                MessRegistration.objects.get_or_create(
                    student=stu,
                    defaults={'hostel': hostel, 'dietary_preference': 'VEG' if i % 2 == 0 else 'NON_VEG', 'is_active': True}
                )

            total_students_count = Student.objects.count()
            vacant_beds_count = Bed.objects.filter(status='VACANT').count()
            self.stdout.write(f"  [OK] Total students created: {total_students_count}. Vacant beds left: {vacant_beds_count}.")

            # 9. Facilities (Shared)
            facilities_data = [
                ('Central University Library', 'Study & Research', 'Multi-storey library with 100,000+ technical volumes, digital journals, and silent air-conditioned reading halls.', 'Central Campus Quad', '24/7 Access'),
                ('Campus Fitness & Gymnasium Suite', 'Health & Fitness', 'Modern fitness equipment, free weights, treadmills, and certified trainers available daily.', 'Sports Complex Annex', '6:00 AM - 10:00 PM'),
                ('Indoor Badminton & Table Tennis Arena', 'Sports', 'Four synthetic badminton courts, Olympic-grade table tennis tables with floodlighting.', 'Student Activity Center', '6:00 AM - 10:30 PM'),
                ('Campus High-Speed Wi-Fi Mesh', 'Connectivity', 'Gigabit WiFi 6 wireless connectivity across all hostel blocks and common zones.', 'All Hostels & Common Grounds', '24/7 Available'),
                ('Campus Health & Wellness Center', 'Medical', 'Resident medical officers, 24/7 emergency nursing station, and dedicated pharmacy.', 'Opposite Boys Hostel A', '24/7 Emergency / OPD 8am-8pm'),
                ('Innovation & Debate Lounge', 'Recreation', 'Modular workspaces, acoustic study pods, and project collaboration desks.', 'Central Student Hub', '8:00 AM - 11:00 PM'),
            ]

            for name, cat, desc, loc, timings in facilities_data:
                Facility.objects.get_or_create(
                    name=name,
                    defaults={'category': cat, 'description': desc, 'location': loc, 'timings': timings, 'is_active': True}
                )
            self.stdout.write("  [OK] Campus Facilities created.")

            # 10. Mess Menus (All 7 days, 4 meals)
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            meals_template = [
                ('BREAKFAST', '7:30 AM - 9:30 AM', {
                    'Monday': 'Idli, Medu Vada, Coconut Chutney, Sambar, Boiled Eggs / Banana, Tea / Coffee',
                    'Tuesday': 'Aloo Paratha with Curd & Pickle, Fresh Sprouts Salad, Boiled Eggs, Tea / Coffee',
                    'Wednesday': 'Poha with Sev, Veg Upma, Coconut Chutney, Omelette / Bananas, Tea / Coffee',
                    'Thursday': 'Puri Bhaji, Fresh Cut Papaya, Boiled Eggs, Tea / Milk / Coffee',
                    'Friday': 'Masala Dosa, Sambar, Tomato Chutney, Boiled Eggs, Tea / Coffee',
                    'Saturday': 'Chole Bhature / Methi Thepla, Mint Chutney, Fresh Fruits, Tea / Coffee',
                    'Sunday': 'Paneer Stuffed Kulcha, Egg Bhurji, Watermelon slices, Special Filter Coffee'
                }),
                ('LUNCH', '12:30 PM - 2:30 PM', {
                    'Monday': 'Steamed Basmati Rice, Dal Tadka, Seasonal Mix Veg, Roti, Cucumber Raita, Gulab Jamun',
                    'Tuesday': 'Jeera Rice, Rajma Masala, Aloo Gobi, Phulka, Curd, Roasted Papad',
                    'Wednesday': 'Peas Pulao, Paneer Butter Masala (Veg) / Chicken Curry (Non-Veg), Dal Fry, Chapati, Salad',
                    'Thursday': 'Lemon Rice, South Indian Sambar, Cabbage Poriyal, Rasam, Appalam, Curd',
                    'Friday': 'Veg Biryani / Egg Biryani, Mirchi Ka Salan, Onion Mint Raita, Phulka, Moong Dal Halwa',
                    'Saturday': 'Steamed Rice, Chana Dal Palak, Bhindi Do Pyaza, Tawa Roti, Boondi Raita',
                    'Sunday': 'Special Hyderabadi Dum Biryani (Chicken / Paneer), Veg Korma, Mirch Salan, Ice Cream'
                }),
                ('SNACKS', '5:00 PM - 6:00 PM', {
                    'Monday': 'Samosa with Mint & Tamarind Chutney, Ginger Masala Tea',
                    'Tuesday': 'Veg Cutlet, Tomato Sauce, Hot Coffee / Green Tea',
                    'Wednesday': 'Onion & Spinach Pakoda, Masala Chai',
                    'Thursday': 'Pav Bhaji with Buttered Pav, Cutting Chai',
                    'Friday': 'Bhel Puri, Sweet Corn Chaat, Lemon Iced Tea / Chai',
                    'Saturday': 'Bun Maska & Biscuits, Filter Coffee',
                    'Sunday': 'Paneer Bread Roll, Adrak Chai'
                }),
                ('DINNER', '7:30 PM - 9:30 PM', {
                    'Monday': 'Phulka, Dal Makhani, Kadai Paneer, Steamed Rice, Green Salad, Kheer',
                    'Tuesday': 'Chapati, Yellow Moong Dal, Dum Aloo Kashmiri, Rice, Fresh Curd, Jalebi',
                    'Wednesday': 'Butter Roti, Dal Tadka, Malai Kofta (Veg) / Egg Curry, Steamed Rice, Salad',
                    'Thursday': 'Roti, Panchratna Dal, Baingan Bharta, Steamed Rice, Papad, Fruit Custard',
                    'Friday': 'Chapati, Dal Palak, Paneer Tikka Masala, Jeera Rice, Rasgulla',
                    'Saturday': 'Roti, Dal Kolhapuri, Mix Veg Korma, Steamed Rice, Tomato Rasam',
                    'Sunday': 'Tandoori Roti, Dal Makhani, Shahi Paneer (Veg) / Butter Chicken, Pulao, Rasmalai'
                }),
            ]

            for m_type, timings, day_map in meals_template:
                for day in days:
                    MessMenu.objects.get_or_create(
                        day_of_week=day,
                        meal_type=m_type,
                        defaults={'items': day_map[day], 'timings': timings, 'is_special': (day == 'Sunday')}
                    )
            self.stdout.write("  [OK] Full 7-day Mess Menus verified.")

            # 11. Laundry Services
            laundry_catalog = [
                ('Regular Wash & Fold', Decimal('25.00'), 'Per Kg', 'Everyday clothes washed, tumble dried, and neatly folded. 24h turnaround.'),
                ('Steam Press & Ironing', Decimal('15.00'), 'Per Item', 'Wrinkle-free professional steam pressing on hangers or folded.'),
                ('Premium Dry Cleaning', Decimal('90.00'), 'Per Item', 'Gentle solvent cleaning for suits, blazers, delicate silks, and formal wear.'),
                ('Bed Linen & Heavy Laundry', Decimal('60.00'), 'Per Set', 'Double bedsheets, duvets, blankets, curtains, and heavy towels.'),
            ]

            for s_name, rate, unit, desc in laundry_catalog:
                LaundryService.objects.get_or_create(
                    service_name=s_name,
                    defaults={'rate_per_unit': rate, 'unit_type': unit, 'description': desc, 'is_active': True}
                )
            self.stdout.write("  [OK] Laundry services catalog verified.")

            # 12. Sample Laundry & Maintenance Requests
            demo_stu1 = Student.objects.get(student_id='STU2026_STUDENT_RAHUL')
            demo_stu2 = Student.objects.get(student_id='STU2026_STUDENT_PRIYA')
            lnd_srv = LaundryService.objects.first()

            LaundryRequest.objects.get_or_create(
                booking_id='LND-2026-0001',
                defaults={
                    'student': demo_stu1,
                    'hostel': demo_stu1.current_hostel,
                    'service': lnd_srv,
                    'item_count_or_weight': Decimal('3.5'),
                    'pickup_slot': timezone.now() - timedelta(days=1),
                    'delivery_slot': timezone.now() + timedelta(days=1),
                    'status': 'PROCESSING',
                    'special_instructions': 'Separate colored shirts from whites please.',
                    'total_cost': Decimal('87.50'),
                }
            )

            MaintenanceRequest.objects.get_or_create(
                complaint_id='MNT-2026-0001',
                defaults={
                    'student': demo_stu1,
                    'hostel': demo_stu1.current_hostel,
                    'room': demo_stu1.current_room,
                    'category': 'ELECTRICAL',
                    'title': 'Study desk reading lamp socket loose',
                    'description': 'The power socket adjacent to bed 1 has an intermittent contact issue.',
                    'priority': 'MEDIUM',
                    'assigned_staff': 'Ramesh Kumar (Hostel Electrician)',
                    'status': 'IN_PROGRESS',
                    'resolution_remarks': 'Inspected wiring. Replacement switch plate ordered.',
                }
            )

            MaintenanceRequest.objects.get_or_create(
                complaint_id='MNT-2026-0002',
                defaults={
                    'student': demo_stu2,
                    'hostel': demo_stu2.current_hostel,
                    'room': demo_stu2.current_room,
                    'category': 'AC',
                    'title': 'AC temperature sensor calibration',
                    'description': 'AC cooling turns off too quickly even at 24C.',
                    'priority': 'HIGH',
                    'assigned_staff': 'CoolAir Service Tech Team',
                    'status': 'REPORTED',
                }
            )

            # 13. Hostel Announcements
            Announcement.objects.get_or_create(
                title='Hostel Room Exchange Window Open for Academic Year 2026-27',
                defaults={
                    'content': 'Eligible students may now propose direct 2-student exchanges or multi-student cyclic exchanges via HostelX. Ensure your dues are clear and submit preferences before Friday.',
                    'target_hostel': None,
                    'author': chief_user,
                    'priority': 'HIGH',
                    'is_active': True,
                }
            )

            Announcement.objects.get_or_create(
                title='Boys Hostel A – Wi-Fi Router Maintenance on Saturday',
                defaults={
                    'content': 'Access points on floors 2 and 3 will undergo firmware upgrades between 10:00 AM and 1:00 PM on Saturday. Alternate connectivity is available in the Study Lounge.',
                    'target_hostel': hostels['H001'],
                    'author': admin_user,
                    'priority': 'NORMAL',
                    'is_active': True,
                }
            )
            self.stdout.write("  [OK] Initial Announcements and Service Requests created.")

        self.stdout.write(self.style.SUCCESS("\nHostelX database seeded successfully! Ready for use."))
