# -*- coding: utf-8 -*-
#
#  ┌────────────────────────────────────────────────────────────────┐
#  │   XARELAM — Sunu Login Log                                     │
#  │   Website  : https://xarelam.com/                              │
#  │   Maintainer : SunuERP-MOD                                     │
#  └────────────────────────────────────────────────────────────────┘

import logging
import ipaddress
import urllib.request
import urllib.error
import json

from odoo import api, models
from odoo.http import request
from user_agents import parse

_logger = logging.getLogger(__name__)

# Délai maximum (secondes) pour l'appel de géolocalisation.
# Valeur courte pour ne pas ralentir la connexion utilisateur.
_GEO_TIMEOUT = 3

# Service de géolocalisation IP gratuit (sans clé API).
# Retourne : status, lat, lon, city, country en français (lang=fr).
_GEO_URL = "http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country&lang=fr"


def _is_private_ip(ip_str):
    """Retourne True si l'adresse IP est privée, loopback ou réservée.

    On ne peut pas géolocaliser une IP privée — on évite l'appel réseau.
    """
    try:
        return ipaddress.ip_address(ip_str).is_private
    except ValueError:
        return True  # IP malformée → on considère non géolocalisable


def _geolocate(ip_str):
    """Interroge ip-api.com pour obtenir lat, lon, ville et pays.

    Retourne un dict avec les clés :
        latitude, longitude, city, country
    ou un dict vide en cas d'échec (IP privée, timeout, API indisponible…).
    """
    if not ip_str or _is_private_ip(ip_str):
        return {}

    url = _GEO_URL.format(ip=ip_str)
    try:
        with urllib.request.urlopen(url, timeout=_GEO_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data.get('status') == 'success':
            return {
                'latitude':  data.get('lat', 0.0),
                'longitude': data.get('lon', 0.0),
                'city':    data.get('city', ''),
                'country': data.get('country', ''),
            }
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        _logger.debug(
            "sunu_login_log: géolocalisation impossible pour %s — %s",
            ip_str, exc,
        )
    return {}


class ResUsers(models.Model):
    """Extension de res.users pour capturer les informations de connexion."""

    _inherit = 'res.users'

    @api.model
    def _check_credentials(self, password, user_agent_env):
        """Surcharge : enregistre un journal à chaque connexion réussie."""
        result = super()._check_credentials(password, user_agent_env)

        try:
            # ── Données réseau ─────────────────────────────────────────────
            ip_address = request.httprequest.environ.get('REMOTE_ADDR', '')
            user_agent_str = request.httprequest.headers.get('User-Agent', '')
            session_id = getattr(request.session, 'sid', None)

            # ── Analyse User-Agent ─────────────────────────────────────────
            ua = parse(user_agent_str)
            if ua.is_mobile:
                device_type = 'Mobile'
            elif ua.is_tablet:
                device_type = 'Tablette'
            elif ua.is_pc:
                device_type = 'Ordinateur'
            elif ua.is_bot:
                device_type = 'Robot'
            else:
                device_type = 'Inconnu'

            # ── Géolocalisation GPS ────────────────────────────────────────
            geo = _geolocate(ip_address)

            # ── Création de l'entrée de journal ───────────────────────────
            vals = {
                'user_id':      self.id,
                'login_email':  self.login,
                'ip_address':   ip_address,
                'user_agent':   user_agent_str,
                'session_id':   session_id,
                'company_id':   self.company_id.id if self.company_id else None,
                'company_name': self.company_id.name if self.company_id else None,
                'db_name':      request.db,
                'lang':         self.lang,
                'tz':           self.tz,
                'is_admin':     self.has_group('base.group_system'),
                'device_type':  device_type,
                'browser':      ua.browser.family,
                'os':           ua.os.family,
                # Géolocalisation (vide si IP privée ou service indisponible)
                'latitude':     geo.get('latitude', 0.0),
                'longitude':    geo.get('longitude', 0.0),
                'city':         geo.get('city', ''),
                'country':      geo.get('country', ''),
            }

            self.env['sunu.login.log'].sudo().create(vals)

        except Exception as exc:
            # On ne bloque jamais la connexion en cas d'erreur de journalisation
            _logger.warning(
                "sunu_login_log: impossible d'enregistrer la connexion — %s", exc
            )

        return result
