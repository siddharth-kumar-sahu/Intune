from django.db import models

from intune.models.base import BaseModel


class Team(BaseModel):
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, related_name="created_teams"
    )

    class Meta:
        db_table = "teams"


class TeamMember(BaseModel):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("staff", "Staff"),
        ("guest", "Guest"),
    ]

    team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="team_members"
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="staff")

    class Meta:
        db_table = "team_members"
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="unique_team_user")
        ]
