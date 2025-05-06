import pygame, time

pygame.mixer.init()
pygame.mixer.music.load("pizza_time.wav")
pygame.mixer.music.play()

# keep script alive long enough to hear it
time.sleep(5)
