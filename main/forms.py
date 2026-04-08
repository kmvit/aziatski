from datetime import date
from django import forms
from .models import BookingRequest
from .pricing import check_overlap


class BookingForm(forms.ModelForm):
    class Meta:
        model = BookingRequest
        fields = ['house', 'name', 'phone', 'check_in', 'check_out', 'guests', 'message']
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date'}),
            'check_out': forms.DateInput(attrs={'type': 'date'}),
            'message': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        check_in = cleaned.get('check_in')
        check_out = cleaned.get('check_out')
        house = cleaned.get('house')

        if check_in and check_out:
            if check_out <= check_in:
                raise forms.ValidationError('Дата выезда должна быть позже даты заезда')
            if check_in < date.today():
                raise forms.ValidationError('Дата заезда не может быть в прошлом')
            if house and check_overlap(house, check_in, check_out):
                raise forms.ValidationError('Выбранные даты уже заняты для этого дома')
        return cleaned
