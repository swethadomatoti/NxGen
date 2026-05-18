from django.core.management.base import BaseCommand
from django.db import transaction
from Demo.models import DemoSchedule
from collections import defaultdict


class Command(BaseCommand):
    help = 'Clean up duplicate demo schedules by removing older duplicates and keeping the latest one'

    def handle(self, *args, **options):
        # Group demos by campaign and scheduled_at to find potential duplicates
        demos_by_campaign_time = defaultdict(list)

        for demo in DemoSchedule.objects.select_related('campaign').order_by('created_at'):
            key = (demo.campaign_id, demo.scheduled_at.date() if demo.scheduled_at else None, demo.scheduled_at.time() if demo.scheduled_at else None)
            demos_by_campaign_time[key].append(demo)

        duplicates_found = 0
        demos_deleted = 0

        for key, demos in demos_by_campaign_time.items():
            if len(demos) > 1:
                duplicates_found += 1
                # Keep the latest demo (by created_at), delete the older ones
                demos_to_delete = sorted(demos, key=lambda x: x.created_at)[:-1]  # All except the last one

                for demo in demos_to_delete:
                    self.stdout.write(
                        f'Deleting duplicate demo ID {demo.id} for campaign {demo.campaign.name} '
                        f'at {demo.scheduled_at} (keeping ID {demos[-1].id})'
                    )
                    demo.delete()
                    demos_deleted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Cleanup complete: Found {duplicates_found} duplicate groups, deleted {demos_deleted} duplicate demos'
            )
        )