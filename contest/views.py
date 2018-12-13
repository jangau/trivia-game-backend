from django.shortcuts import render


def game_view(request):
    return render(request, "game_display.html")


def gamemaster_view(request):
    return render(request, 'game_master.html')
