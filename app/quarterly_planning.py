"""Headless quarterly presentation controller. All authority belongs to Session."""
from game.scheduling.quarterly_commands import CreateQuarterlyService, ReviseQuarterlyFare
from game.scheduling.quarterly_edits import (
    ReviseQuarterlySlot, AddQuarterlyFrequency, RemoveQuarterlySlots,
    ContinueQuarterlySlot, ReplaceQuarterlyService, RetireQuarterlyService)
from game.scheduling.quarterly_publication import PublishQuarterlyPlan


class QuarterlyPlanningController:
    def __init__(self, session):
        self.session=session; self.binding=None; self.plan_id=None; self.offset=0
        self.selected=None; self.page=None; self.readiness=None; self.confirmation=None
        self.issues=(); self.last_published=None
        self.aircraft_id=None

    def refresh(self):
        binding=self.session.binding_revision
        if binding != self.binding:
            self.plan_id=None; self.offset=0; self.selected=None
            self.readiness=None; self.confirmation=None; self.issues=(); self.last_published=None
            self.aircraft_id=None
            self.binding=binding
        page=self.session.quarterly_planning_page(self.plan_id,offset=self.offset)
        if self.page is not None and (page['time_utc'],page['revision'],page['plan_id']) != (
                self.page['time_utc'],self.page['revision'],self.page['plan_id']):
            self.selected=None; self.readiness=None
        self.page=page
        return page

    def select_plan(self, identity=None):
        self.plan_id=identity; self.offset=0; self.selected=None
        self.readiness=None; self.confirmation=None; self.issues=()
        return self.refresh()

    def select_slot(self, key):
        self.refresh()
        if not any((r['service_id'],r['slot_number']) == key for r in self.page['rows']):
            raise ValueError('select a service on the current page')
        self.selected=key

    def _target(self):
        if self.binding != self.session.binding_revision:
            self.refresh()
            raise ValueError('career was replaced; select again')
        if self.page is None: self.refresh()
        if not self.page['editable']: raise ValueError('this quarter is locked; use eligible planning')
        return self.page['plan_id'],self.page['revision']

    def execute(self, request):
        self.confirmation=None
        prepared=self.session.prepare_quarterly_command(request)
        result=prepared if not prepared.succeeded else self.session.apply_quarterly_command(prepared.prepared)
        self.issues=result.issues
        if result.succeeded:
            self.plan_id=result.weekly_plan_id or self.plan_id
            self.selected=None; self.readiness=None; self.refresh()
        return result

    def create(self, slot, prefix):
        pid,revision=self._target()
        return self.execute(CreateQuarterlyService(self.page['selected_quarter'],prefix,slot,pid,revision))

    def edit(self, changes):
        pid,revision=self._target()
        if not self.selected: raise ValueError('select an existing frequency')
        return self.execute(ReviseQuarterlySlot(pid,revision,*self.selected,changes))

    def fare(self, amount_minor):
        pid,revision=self._target()
        if not self.selected: raise ValueError('select an existing frequency')
        return self.execute(ReviseQuarterlyFare(pid,revision,*self.selected,
            {'currency':'USD','amount_minor':amount_minor}))

    def add_frequency(self, slot):
        pid,revision=self._target()
        if not self.selected: raise ValueError('select a service')
        return self.execute(AddQuarterlyFrequency(pid,revision,self.selected[0],slot))

    def remove(self):
        pid,revision=self._target()
        if not self.selected: raise ValueError('select an existing frequency')
        return self.execute(RemoveQuarterlySlots(pid,revision,(self.selected,)))

    def retire(self, service_id):
        pid,revision=self._target()
        return self.execute(RetireQuarterlyService(pid,revision,service_id))

    def replace(self, slot, prefix):
        pid,revision=self._target()
        if not self.selected: raise ValueError('select a service to replace')
        return self.execute(ReplaceQuarterlyService(pid,revision,self.selected[0],prefix,slot))

    def continue_slot(self, source, slot):
        pid,revision=self._target()
        return self.execute(ContinueQuarterlySlot(pid,revision,source['plan_id'],source['revision'],
            source['revision'],slot['service_id'],slot['slot_number'],{},self.page['selected_quarter']))

    def inspect(self):
        self.refresh()
        if self.page['plan_id'] is None and self.page['fence'] and self.page['fence']['failure']:
            raise ValueError('Initialize the fenced unpublished plan from its baseline or create a service before inspecting readiness; use Retry publication for the outstanding obligation')
        self.readiness=self.session.quarterly_publication_readiness(self.page['plan_id'],
            expected_revision=self.page['revision'],expected_time_utc=self.page['time_utc'])
        return self.readiness

    def prepare_publication(self):
        self.refresh(); self._target()
        if self.page['fence'] and self.page['fence']['failure']:
            raise ValueError('correct the fenced quarter, then use Retry publication')
        result=self.session.prepare_quarterly_command(PublishQuarterlyPlan('MANUAL',
            self.page['selected_quarter'],self.page['plan_id'],self.page['revision'],self.page['time_utc']))
        self.issues=result.issues
        self.confirmation=result.prepared if result.succeeded else None
        return result

    def confirm_publication(self):
        if self.binding != self.session.binding_revision or self.confirmation is None:
            self.confirmation=None
            raise ValueError('publication confirmation expired; review again')
        prepared=self.confirmation; self.confirmation=None
        result=self.session.apply_quarterly_command(prepared)
        self.issues=result.issues
        if result.succeeded:
            self.last_published=result.weekly_plan_id
            self.select_plan()
        return result

    def retry(self):
        if self.binding != self.session.binding_revision:
            self.refresh(); raise ValueError('career was replaced; review the saved fence')
        report=self.session.retry_quarterly_publication()
        self.plan_id=None; self.selected=None; self.readiness=None; self.confirmation=None
        self.refresh()
        return report
