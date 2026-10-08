# -*- coding: utf-8 -*-
#
#  ┌────────────────────────────────────────────────────────────────┐
#  │   XARELAM — Sunu Login Log                                     │
#  │   Website  : https://xarelam.com/                              │
#  │   Maintainer : SunuERP-MOD                                     │
#  └────────────────────────────────────────────────────────────────┘

from odoo import api, fields, models


class SunuLoginLog(models.Model):
    """Journal d'audit des connexions utilisateurs Odoo.

    Enregistre pour chaque connexion :
      - l'identité de l'utilisateur
      - l'adresse IP et les coordonnées GPS (latitude / longitude)
      - la ville et le pays détectés par géolocalisation IP
      - le type d'appareil, le navigateur et le système d'exploitation
      - l'identifiant de session et l'horodatage
    """

    _name = 'sunu.login.log'
    _description = 'Journal de Connexion Utilisateur'
    _rec_name = 'name'
    _order = 'login_time desc'
    _log_access = True

    # ── Résumé calculé ────────────────────────────────────────────────────
    name = fields.Char(
        string="Résumé",
        compute="_compute_name",
        store=True,
    )

    # ── Identité ──────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users',
        string="Utilisateur",
        ondelete="set null",
        index=True,
    )
    login_email = fields.Char(
        string="Email de connexion",
        required=True,
        index=True,
    )
    is_admin = fields.Boolean(string="Administrateur")

    # ── Horodatage & session ──────────────────────────────────────────────
    login_time = fields.Datetime(
        string="Date / Heure de connexion",
        default=lambda self: fields.Datetime.now(),
        required=True,
        index=True,
    )
    session_id = fields.Char(string="Identifiant de session")

    # ── Réseau ────────────────────────────────────────────────────────────
    ip_address = fields.Char(string="Adresse IP")

    # ── Géolocalisation GPS ───────────────────────────────────────────────
    latitude = fields.Float(
        string="Latitude",
        digits=(10, 6),
        help="Coordonnée GPS latitude du lieu de connexion (via géolocalisation IP).",
    )
    longitude = fields.Float(
        string="Longitude",
        digits=(10, 6),
        help="Coordonnée GPS longitude du lieu de connexion (via géolocalisation IP).",
    )
    city = fields.Char(
        string="Ville",
        help="Ville détectée par géolocalisation de l'adresse IP.",
    )
    country = fields.Char(
        string="Pays",
        help="Pays détecté par géolocalisation de l'adresse IP.",
    )

    # ── Appareil & navigateur ─────────────────────────────────────────────
    device_type = fields.Char(string="Type d'appareil")
    browser = fields.Char(string="Navigateur")
    os = fields.Char(string="Système d'exploitation")
    user_agent = fields.Text(string="Chaîne User-Agent")

    # ── Contexte Odoo ─────────────────────────────────────────────────────
    company_id = fields.Many2one('res.company', string="Société")
    company_name = fields.Char(string="Nom de la société")
    db_name = fields.Char(string="Base de données")
    lang = fields.Char(string="Langue")
    tz = fields.Char(string="Fuseau horaire")

    # ── Calcul du résumé ──────────────────────────────────────────────────
    @api.depends('login_email', 'login_time', 'ip_address', 'city', 'country')
    def _compute_name(self):
        for rec in self:
            time_str = (
                rec.login_time.strftime('%d/%m/%Y %H:%M:%S')
                if rec.login_time else 'Heure inconnue'
            )
            location_parts = [p for p in [rec.city, rec.country] if p]
            location = ', '.join(location_parts) if location_parts else (rec.ip_address or 'IP inconnue')
            user_name = rec.user_id.name if rec.user_id else 'Inconnu'
            rec.name = f"{user_name} — {time_str} — {location}"

    # ── Lien Google Maps ──────────────────────────────────────────────────
    google_maps_url = fields.Char(
        string="Voir sur Google Maps",
        compute="_compute_google_maps_url",
        help="Lien Google Maps pointant vers les coordonnées GPS de la connexion.",
    )

    @api.depends('latitude', 'longitude')
    def _compute_google_maps_url(self):
        for rec in self:
            if rec.latitude and rec.longitude:
                rec.google_maps_url = (
                    f"https://www.google.com/maps?q={rec.latitude},{rec.longitude}"
                    f"&z=14"
                )
            else:
                rec.google_maps_url = False
