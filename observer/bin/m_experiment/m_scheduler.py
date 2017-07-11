# -*- coding: utf-8 -*-
"""

`author`    :   Quentin Lampin <quentin.lampin@orange.com>
`license`   :   MPL
`date`      :   2015/10/12
Copyright 2015 Orange

SensorLab scheduler
---------------------------------

`Requires python 3.2 or above`

@author: Quentin Lampin <quentin.lampin@orange.com>



"""

import time
import datetime
import threading
import re
from pydispatch import dispatcher
from .. import m_common

ON_LAST_EVENT_COMPLETION = 'on_last_event_completion'
ORIGIN = 'origin'

# node states
SCHEDULER_UNDEFINED = 0
SCHEDULER_READY = 1
SCHEDULER_HALTED = 2
SCHEDULER_RUNNING = 3
SCHEDULER_STATES = ('undefined', 'ready', 'halted', 'running')

# default values
SCHEDULE_UNDEFINED = 'undefined'
REMAINING_UNDEFINED = 'undefined'
END_UNDEFINED = 'undefined'

# recognized evt actions
SCHEDULER_ACTIONS = [
    m_common.COMMAND_LOAD,
    m_common.COMMAND_INIT,
    m_common.COMMAND_START,
    m_common.COMMAND_STOP,
    m_common.COMMAND_RESET,
    m_common.COMMAND_SEND
]


class Scheduler:
    """docstring for scheduler"""

    def __init__(self):
        self.regex = re.compile(r'((?P<days>\d+?)d)?((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')
        self.actions = {
            m_common.COMMAND_LOAD: "experiment.node.{0}".format(m_common.COMMAND_LOAD),
            m_common.COMMAND_INIT: "experiment.node.{0}".format(m_common.COMMAND_INIT),
            m_common.COMMAND_START: "experiment.node.{0}".format(m_common.COMMAND_START),
            m_common.COMMAND_STOP: "experiment.node.{0}".format(m_common.COMMAND_STOP),
            m_common.COMMAND_RESET: "experiment.node.{0}".format(m_common.COMMAND_RESET),
            m_common.COMMAND_SEND: "experiment.node.{0}".format(m_common.COMMAND_SEND)
        }
        self.state = SCHEDULER_UNDEFINED
        self.alive = False
        self.thread = None
        self.schedule = None
        self.beginning = None
        self.estimated_duration = None
        self.remaining = None
        self.last_time = None
        self.on_complete_callback = None
        self.step = datetime.timedelta(seconds=1)  # 1 sec

    def setup(self, schedule):
        # validate schedule
        if any(event['action'] not in SCHEDULER_ACTIONS for event in schedule):
            faulty_events = filter(lambda evt: evt['action'] not in SCHEDULER_ACTIONS, schedule)
            raise m_common.ExperimentSetupException(m_common.ERROR_CONFIGURATION_UNKNOWN_ITEM.format(faulty_events))
        self.schedule = schedule
        self.estimated_duration = datetime.timedelta(seconds=0)
        for event in schedule:
            sleep_s = 0
            tokens = self.regex.match(event['time'])
            if tokens:
                tokens_dict = tokens.groupdict()
                parameters = {}
                for key, value in tokens_dict.items():
                    if value:
                        parameters[key] = int(value)
                    else:
                        parameters[key] = 0
                sleep_s = datetime.timedelta(**parameters)
            self.estimated_duration += sleep_s
        self.state = SCHEDULER_READY

    def status(self):
        return {
            'state': SCHEDULER_STATES[self.state],
            'remaining': self._remaining_status() if self.last_time else REMAINING_UNDEFINED,
            'end': self._end_status() if self.last_time else END_UNDEFINED,
            'schedule': self.schedule if self.schedule else SCHEDULE_UNDEFINED}

    def start(self, on_complete_callback):
        self.alive = True
        self.beginning = time.time()
        self.remaining = self.estimated_duration
        self.last_time = self.beginning

        self.on_complete_callback = on_complete_callback
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def stop(self):
        if self.alive:
            self.alive = False
            self.thread.join()

    def _remaining_status(self):
        timedelta = self.remaining - datetime.timedelta(seconds=(time.time() - self.last_time))
        return str(timedelta)

    def _end_status(self):
        timedelta = self.remaining - datetime.timedelta(seconds=(time.time() - self.last_time))
        end = datetime.datetime.now() + timedelta
        return str(end)

    def _run(self):
        for event in self.schedule:
            if self.alive:
                if event['time'] not in [ON_LAST_EVENT_COMPLETION, ORIGIN]:
                    tokens = self.regex.match(event['time'])
                    if tokens:
                        tokens_dict = tokens.groupdict()
                        parameters = {}
                        for key, value in tokens_dict.items():
                            if value:
                                parameters[key] = int(value)
                            else:
                                parameters[key] = 0
                        sleep_s = datetime.timedelta(**parameters)
                        while self.alive and sleep_s.total_seconds() > 0:
                            sleep_step = min(self.step, sleep_s)
                            time.sleep(sleep_step.total_seconds())
                            sleep_s -= sleep_step
                            self.remaining -= sleep_step
                        # sleep_s = datetime.timedelta(**parameters)
                        # self.remaining -= sleep_s
                        # time.sleep(sleep_s.total_seconds())
                    else:
                        self.stop()
                        break
                if 'parameters' in event.keys():
                    print('action: {0} parameters: {1}'.format(event['action'], event['parameters']))
                    dispatcher.send(self.actions[event['action']], sender=self, **event['parameters'])
                else:
                    print('action: {0}'.format(event['action']))
                    dispatcher.send(self.actions[event['action']], sender=self)
                self.last_time = time.time()
            else:
                # terminate the thread
                break
        if self.alive:
            self.alive = False
            self.remaining = 0
            self.remaining = None
            self.on_complete_callback()
        else:
            self.remaining = 0
            self.last_time = None
            # self.alive = False
            # self.remaining = 0
            # self.last_time = None
            # self.on_complete_callback()
