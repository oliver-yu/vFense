class ScheduleDefaults(object):
    TIME_ZONE = 'UTC'

class ScheduleTriggers(object):
    CRON = 'cron'
    INTERVAL = 'interval'
    DATE = 'date'

    @staticmethod
    def get_valid_triggers():
        valid_triggers = (
            map(
                lambda x:
                getattr(ScheduleTriggers, x), dir(ScheduleTriggers)[:-3]
            )
        )
        return valid_triggers


class ScheduleVariables(object):
    Function = 'function'