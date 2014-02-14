"""
    Schedule the execution of an async task.
"""
from datetime import timedelta
# No name 'sha1' in module 'hashlib'
# pylint: disable=E0611
from hashlib import sha1
from simplejson import dumps

from django.db.models import Q
try:
    # No name 'timezone' in module 'django.utils'
    # pylint: disable=E0611
    from django.utils import timezone
except ImportError:
    from datetime import datetime as timezone

from async.models import Error, Job, Group
from async.utils import full_name


def _get_today_dt():
    """Get today datetime, testing purpose.
    """
    return timezone.now()


def schedule(function, args=None, kwargs=None,
        priority=5, run_after=None, group=None, meta=None):
    """Schedule a tast for execution.
    """
    # Too many arguments
    # pylint: disable=R0913
    if group:
        expected_group = Group.objects.filter(reference=group).latest('created')
    else:
        expected_group = None
    job = Job(
        name=full_name(function),
            args=dumps(args or []), kwargs=dumps(kwargs or {}),
        meta=dumps(meta or {}), scheduled=run_after,
        priority=priority,
        group=expected_group
        )
    job.save()
    return job


def deschedule(function, args=None, kwargs=None):
    """Remove any instances of the job from the queue.
    """
    job = Job(
        name=full_name(function),
            args=dumps(args or []), kwargs=dumps(kwargs or {}))
    mark_executed = Job.objects.filter(executed=None,
        identity=sha1(unicode(job)).hexdigest())
    mark_executed.update(executed=_get_today_dt())


def health():
    """Return information about the health of the queue in a format that
    can be turned into JSON.
    """
    output = {'queue': {}, 'errors': {}}
    output['queue']['all-jobs'] = Job.objects.all().count()
    output['queue']['not-executed'] = Job.objects.filter(executed=None).count()
    output['queue']['executed'] = Job.objects.exclude(executed=None).count()
    output['errors']['number'] = Error.objects.all().count()
    return output


def remove_old_jobs(remove_jobs_before_days=30, resched_hours=8):
    """Remove old jobs start from these conditions

    Removal date for jobs is `remove_jobs_before_days` days earlier
    than when this is executed.

    It will delete jobs and groups that meet the following:
    - Jobs execute before the removal date and which are not in any group.
    - Groups (and their jobs) where all jobs have executed before the removal
        date.
    """
    start_remove_jobs_before_dt = _get_today_dt() - timedelta(
        days=remove_jobs_before_days)

    Job.objects.filter(Q(group__isnull=True), Q(executed__isnull=False),
        Q(executed__lt=start_remove_jobs_before_dt)).delete()
    groups = Group.objects.filter(Q(jobs__executed__isnull=False))
    for group in groups.iterator():
        group.jobs.all().delete()
        group.delete()

    next_exec = _get_today_dt() + timedelta(hours=resched_hours)

    schedule(remove_old_jobs,
        args=[remove_jobs_before_days, resched_hours],
        run_after=next_exec)
