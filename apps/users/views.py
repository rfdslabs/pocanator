from django.shortcuts import render, redirect
from django.views.generic import TemplateView, UpdateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages

from .models import UserProfile, APIUsage
from .forms import UserProfileForm, APIKeyForm


class UserProfileView(LoginRequiredMixin, TemplateView):
    """View to display user profile"""
    template_name = 'users/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.request.user.profile
        return context


class UserProfileEditView(LoginRequiredMixin, UpdateView):
    """View to edit user profile"""
    model = UserProfile
    template_name = 'users/profile_edit.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('user-profile')
    
    def get_object(self):
        return self.request.user.profile
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)


class APIKeyView(LoginRequiredMixin, FormView):
    """View to manage API keys"""
    template_name = 'users/api_key.html'
    form_class = APIKeyForm
    success_url = reverse_lazy('api-key')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['api_key'] = self.request.user.profile.api_key
        return context
    
    def form_valid(self, form):
        profile = self.request.user.profile
        if form.cleaned_data.get('regenerate_key'):
            profile.api_key = UserProfile.generate_api_key()
            profile.save()
            messages.success(self.request, 'API key regenerated successfully.')
        return super().form_valid(form)


class APIUsageView(LoginRequiredMixin, TemplateView):
    """View to display API usage"""
    template_name = 'users/api_usage.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['api_usage'] = APIUsage.objects.filter(user=self.request.user).order_by('-timestamp')
        
        # Calculate total tokens and cost
        total_tokens = sum(usage.tokens_used for usage in context['api_usage'])
        total_cost = sum(usage.cost for usage in context['api_usage'])
        
        context['total_tokens'] = total_tokens
        context['total_cost'] = total_cost
        
        return context