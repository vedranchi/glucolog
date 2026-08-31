import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from logs.models import GlucoseLog, InsulinLog, MealLog
from users.models import HealthProfile, UserPreferences

User = get_user_model()

GLUCOSE_NOTES = ["before workout", "felt a bit off", "stressful day", "travel day"]


def dec(value, places="0.01"):
    return Decimal(str(round(value, 4))).quantize(Decimal(places))


class Command(BaseCommand):
    """Seed a demo account with plausible, backdated logs for screenshots/demos.

    Synthetic data only — never point this at production. Existing demo logs
    are hard-deleted on --reset rather than soft-deleted, because this is
    throwaway fixture data, not a real patient's history.
    """

    help = "Seed a demo user with realistic glucose/insulin/meal history for screenshots."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demo@glucoread.app")
        parser.add_argument("--password", default="Demo1234!")
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete this demo user's existing logs before seeding.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running even when DEBUG is off.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "Refusing to seed demo data outside DEBUG (looks like production). "
                "Pass --force if you're certain this is safe."
            )

        random.seed(options["seed"])

        user = User.objects.filter(email=options["email"]).first()
        created = user is None
        if created:
            # Identity here is the email -- it is the USERNAME_FIELD. But
            # AbstractUser still carries a unique `username`, and the obvious
            # one may already be taken: the demo address changed with the
            # GlucoRead rename, so any install seeded before it has a `demo`
            # row under the old address. Deriving the username blindly turned
            # a re-seed into an IntegrityError on exactly the machines that had
            # used this command before.
            base = options["email"].split("@")[0]
            username = base
            suffix = 1
            while User.objects.filter(username=username).exists():
                suffix += 1
                username = f"{base}{suffix}"
            user = User.objects.create(email=options["email"], username=username)
        user.set_password(options["password"])
        user.save()

        UserPreferences.objects.get_or_create(user=user)
        HealthProfile.objects.update_or_create(
            user=user, defaults={"diabetes_type": HealthProfile.DIABETES_TYPE_1}
        )

        if options["reset"]:
            GlucoseLog.objects.filter(user=user).delete()
            InsulinLog.objects.filter(user=user).delete()
            MealLog.objects.filter(user=user).delete()

        days = options["days"]
        now = timezone.now()
        # Build timestamps in the display timezone: replacing the hour on a UTC
        # datetime would shift every reading by the UTC offset, so a "22:30
        # bedtime" value would surface on the next day's screen.
        now_local = timezone.localtime(now)
        glucose_count = insulin_count = meal_count = 0

        # range() ends at 0, not 1 — today gets partial data (up to the current
        # hour) so the dashboard's "Today" cards and Recent Activity aren't empty.
        for day_offset in range(days, -1, -1):
            day = now_local - timedelta(days=day_offset)

            def at(hour, minute=None):
                minute = random.randint(0, 25) if minute is None else minute
                return day.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # --- glucose: fasting, before/after lunch, before dinner, bedtime ---
            readings = [
                ("fasting", at(7), random.gauss(5.4, 0.6)),
                ("before meal", at(12), random.gauss(5.8, 0.7)),
                ("after meal", at(14), random.gauss(8.6, 1.3)),
                ("before meal", at(18, 30), random.gauss(6.0, 0.8)),
                ("bedtime", at(22, 30), random.gauss(6.3, 0.9)),
            ]
            # the occasional out-of-range excursion reads as organic, not staged
            if random.random() < 0.15:
                readings.append(("other", at(16), random.gauss(12.5, 1.0)))

            for context, when, raw_value in readings:
                if when > now_local:  # today's later entries haven't happened yet
                    continue
                value = max(3.5, min(raw_value, 15.0))
                note = random.choice(GLUCOSE_NOTES) if random.random() < 0.15 else None
                GlucoseLog.objects.create(
                    user=user,
                    value=dec(value, "0.001"),
                    context=context,
                    measured_at=when,
                    note=note,
                )
                glucose_count += 1

            # --- meals: breakfast/lunch/dinner always, snack sometimes ---
            meals = [
                ("breakfast", at(7, 15), random.gauss(42, 8)),
                ("lunch", at(12, 15), random.gauss(55, 10)),
                ("dinner", at(18, 45), random.gauss(50, 9)),
            ]
            if random.random() < 0.3:
                meals.append(("snack", at(16, 15), random.gauss(18, 6)))

            for context, when, carbs in meals:
                if when > now_local:
                    continue
                carbs = max(5, carbs)
                protein = max(5, random.gauss(carbs * 0.35, 4))
                fats = max(3, random.gauss(carbs * 0.3, 3))
                calories = carbs * 4 + protein * 4 + fats * 9
                MealLog.objects.create(
                    user=user,
                    context=context,
                    eaten_at=when,
                    carbs=dec(carbs, "0.1"),
                    protein=dec(protein, "0.1"),
                    fats=dec(fats, "0.1"),
                    calories=dec(calories, "0.1"),
                )
                meal_count += 1

                # bolus roughly tracks carbs, ~1 unit per 10g with some noise
                if context != "snack":
                    InsulinLog.objects.create(
                        user=user,
                        insulin_type="bolus",
                        units=dec(max(1, carbs / 10 + random.gauss(0, 0.5)), "0.1"),
                        taken_at=when - timedelta(minutes=10),
                    )
                    insulin_count += 1

            # --- basal: once daily ---
            basal_at = at(22, 0)
            if basal_at <= now_local:
                InsulinLog.objects.create(
                    user=user,
                    insulin_type="basal",
                    units=dec(random.gauss(20, 1.5), "0.1"),
                    taken_at=basal_at,
                )
                insulin_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Reused'} demo user {user.email} "
                f"(password: {options['password']}).\n"
                f"Seeded {glucose_count} glucose, {insulin_count} insulin, "
                f"{meal_count} meal logs over the last {days} days."
            )
        )
