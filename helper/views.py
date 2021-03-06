from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import UpdateView, DeleteView, CreateView
from django.http import Http404, HttpResponseNotAllowed, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse, reverse_lazy

from formtools.wizard.views import SessionWizardView
from stronghold.decorators import public

from .models import AgentConfig, TaskPair
from .forms import (AgentConfigUpdateForm, AgentConfigCreateForm,
                    TaskPairUpdateForm, TaskPairAdvancedForm,
                    TaskPairChooseCauseAgentForm, TaskPairChooseCauseTaskForm,
                    TaskPairChooseEffectAgentForm, TaskPairChooseEffectTaskForm,
                    TaskPairCauseOptionsForm, TaskPairEffectOptionsForm,
                    )



class AgentConfigListView(ListView):
    model = AgentConfig


class AgentConfigDetailView(UpdateView):
    model = AgentConfig
    template_name_suffix = '_detail'
    form_class = AgentConfigUpdateForm

    def get_success_url(self):
        return self.object.get_absolute_url()


class AgentConfigDeleteView(DeleteView):
    model = AgentConfig
    success_url = reverse_lazy('agent_config_list')

    def get_context_data(self, **kwargs):
        context = super(AgentConfigDeleteView, self).get_context_data(**kwargs)
        context['cascade_task_pairs'] = TaskPair.objects.filter(
            Q(cause_agent=self.object) | Q(effect_agent=self.object)
        ).distinct()
        return context

class AgentConfigCreateView(CreateView):
    model = AgentConfig
    form_class = AgentConfigCreateForm


class TaskPairListView(ListView):
    model = TaskPair


class TaskPairDeleteView(DeleteView):
    model = TaskPair
    success_url = reverse_lazy('task_pair_list')


class TaskPairCreateView(CreateView):
    model = TaskPair
    form_class = TaskPairAdvancedForm
    template_name = 'helper/taskpair_detail.html'


class TaskPairWizard(SessionWizardView):
    form_list = [TaskPairChooseCauseAgentForm, TaskPairChooseCauseTaskForm,
                 TaskPairCauseOptionsForm,
                 TaskPairChooseEffectAgentForm, TaskPairChooseEffectTaskForm,
                 TaskPairEffectOptionsForm,
                 ]
    template_name = 'helper/taskpair_wizard.html'


    def render_done(self, form, **kwargs):
        """
        Dont' want all the revalidation storage stuff... The form is fine :)
        """
        task_pair = TaskPair.objects.create(**form.cleaned_data)
        task_pair.populate_dedup_events()
        return redirect(task_pair)

    def process_step(self, form):
        """
        user cleaned_data as next forms initial data
        """
        if self.steps.next:
            self.initial_dict.setdefault(self.steps.next, {}).update({
                k: v.pk if hasattr(v, 'pk') else v
                for k, v in form.cleaned_data.items()})


class TaskPairDetailView(UpdateView):
    model = TaskPair
    template_name_suffix = '_detail'
    form_class = TaskPairUpdateForm

    def get_success_url(object):
        return reverse('task_pair_list')

class TaskPairAdvancedDetailView(UpdateView):
    model = TaskPair
    template_name_suffix = '_detail'
    form_class = TaskPairAdvancedForm

    def get_success_url(object):
        return reverse('task_pair_list')


def dispatch_agent_config_url(request, agent_config_id, view_name):
    agent_config = get_object_or_404(AgentConfig, pk=agent_config_id)
    if view_name not in agent_config.agent.action_config_options:
        raise Http404
    view = agent_config.agent.action_config_options[view_name]
    return view.as_view()(request, agent_config)


@public
@csrf_exempt
def dispatch_task_pair_url(request, task_pair_id, secret):
    task_pair = get_object_or_404(TaskPair, id=task_pair_id)
    try:
        if request.method == 'POST':
            view = task_pair.cause_view
            assert task_pair.cause_agent.options.get('secret') == secret
        elif request.method == 'GET':
            view = task_pair.effect_view
            assert task_pair.effect_agent.options.get('secret') == secret
        else:
            return HttpResponseNotAllowed(['POST', 'GET'])
    except (AttributeError, ImportError):
        raise Http404
    except AssertionError:
        return HttpResponseForbidden()
    else:
        return view(request, task_pair)
