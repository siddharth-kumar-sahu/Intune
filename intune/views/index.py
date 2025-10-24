from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from intune.models import Team


class IndexView(LoginRequiredMixin, View):
    def get(self, request):
        teams = Team.objects.filter(members__user=request.user)
        context = {
            "teams": teams,
        }
        return render(request, "index.html", context)
