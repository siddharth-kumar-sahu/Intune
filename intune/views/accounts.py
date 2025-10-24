from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth import login, logout

from intune.models import User


class LoginView(View):
    def get(self, request):
        return render(request, "accounts/login.html")

    def post(self, request):
        login_data = request.POST
        email = login_data.get("email")
        password = login_data.get("password")

        user = User.objects.filter(email=email).first()
        if user is None:
            messages.warning(request, "No user found with this email.")
            return render(request, "accounts/login.html")

        if not user.check_password(password):
            messages.warning(request, "Incorrect password.")
            return render(request, "accounts/login.html")

        login(request, user)
        return redirect("index")


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("login")
