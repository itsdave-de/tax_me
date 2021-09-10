# -*- coding: utf-8 -*-
# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime as dt

from frappe.utils import password
import pymssql
import re

class UmsatzsteuerVoranmeldung(Document):
	#Regex für das Prüfen auf plausibles Datum
	epic_date_regex = r"^(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})$"

	def berechnen(self):
		settings = frappe.get_single("Tax Me Einstellungen")

		#Ausgangsbelege verarbeiten

		si_list = frappe.get_all(
			"Sales Invoice", 
			filters={
				"docstatus": 1,
				"posting_date": ["between", [self.von, self.bis]]
				},
			fields = ["name", "posting_date", "total", "total_taxes_and_charges"]
			)
		summe_netto = 0
		summe_steuern = 0
		for si in si_list:
			summe_netto += si["total"]
			summe_steuern += si["total_taxes_and_charges"]
		self.summe_netto = summe_netto
		self.summe_umsatzsteuer = summe_steuern

		#Eingangsbelege verarbeiten

		pi_list = self.get_eingangsrechnungen_from_inoxision(settings)

		summe_netto_pi = 0
		summe_steuern_pi = 0
		for pi in pi_list:
			summe_netto_pi += pi["NettoBeleg"]
			summe_steuern_pi += pi["Ust"]
		
		self.summe_netto_pi = summe_netto_pi
		self.summe_steuern_pi = summe_steuern_pi

		self.status = "draft"
		self.save()
	
	def get_eingangsrechnungen_from_inoxision(self, settings):
		#MSSSQL Source Data
		conn = pymssql.connect(
			host=settings.server,
			user=settings.benutzer,
			password=settings.passwort,
			database=settings.datenbank
			)

		####end config####
		cursor = conn.cursor(as_dict=True)

		#SQL Abfrage, filtert versteckte Dokumente raus.
		#Zusätzlich wird noch aus einer Hilfstabelle [LIEFERANTEN-NR] die Kreditorennummer ergänzt.
		#Wir holen hier alle Belege aus der Datenbank, da das Datum nicht a.G. der varchar Feldes
		#nicht gut gefilter werden kann.

		query = r"""SELECT 
						b.Belegart
						,b.AdressName
						,b.AdressPLZ
						,b.AdressOrt
						,b.AdressNr
						,b.BelegDatum
						,b.BelegNummer
						,b.NettoBeleg
						,b.Ust
						,b.Zahltage
						,b.Zahlungsart
						,l.Kundennummer
						,l.Kreditorennummer
						,b.Erlöskonto
						,d.ishidden
						,b.UID
					FROM [Adpt_Adptgmbh].[dbo].[U_Belege] b
					LEFT OUTER JOIN [Adpt_itsdave].[dbo].[LIEFERANTEN-NR] l
						ON b.AdressName = l.Name
					LEFT OUTER JOIN [Adpt_Adptgmbh].[dbo].[_Docs] d
						ON b.UID = d.UID
					WHERE (Belegart = 'Rechnung' or Belegart = 'Dauerrechnung' or Belegart = 'Gutschrift' )
						AND d.ishidden = 0"""


		cursor.execute(query)
		if cursor.rowcount == 0:
			frappe.throw("Keine Inoxision Belege gefunden.")
		return_list = []
		for row in cursor:
			#print(row)
			belegdatum_dt = dt
			#Checks auf plausibles Datumsformat, da das Inoxision Feld nur varchar ist
			#Wenn ein Beleg fehlerhaft ist, brechen wir mit Meldung für den Unser ab.
			if not re.match(self.epic_date_regex,row["BelegDatum"]):
				frappe.throw("Datum in Beleg kann nicht interpretiert werden. Bitte den Beleg in Inoxision korrigieren:<br>" + str(row))
				return False
			try:
				#Versuch, dt mit 4-stelligem Jahr zu parsen
				belegdatum_dt =  dt.strptime(row["BelegDatum"], "%d.%m.%Y")
			except ValueError as e:
				if "time data" in str(e) and "does not match format" in str(e):
					try:
						#Versuch, dt mit 2-stelligem Jahr zu parsen
						belegdatum_dt =  dt.strptime(row["BelegDatum"], "%d.%m.%y")
						print("2 stellen bei: " + row["BelegNummer"] + " " + row["AdressName"] + " " + row["BelegDatum"])
					except:
						frappe.throw("Datum in Beleg kann nicht interpretiert werden. Bitte den Beleg in Inoxision korrigieren:<br>" + str(row))
			
			#Checks auf plausibles Zahlenformat
			row["NettoBeleg"] = self.parse_string_to_float(row["NettoBeleg"])
			if (isinstance(row["NettoBeleg"], bool)) and (row["NettoBeleg"] == False):
				frappe.msgprint(str(row["NettoBeleg"]) + " kann nicht als Zahl interpretiert werden:" + str(row))
						
			row["Ust"] = self.parse_string_to_float(row["Ust"])
			if (isinstance(row["Ust"], bool)) and (row["Ust"] == False):
				frappe.msgprint(str(row["Ust"]) + " kann nicht als Zahl interpretiert werden:" + str(row))

			#Datum Prüfen, wir geben nur Belege innerhalb des gewählten Zeitraums zurück
			if belegdatum_dt >= dt.fromisoformat(self.von) and belegdatum_dt <= dt.fromisoformat(self.bis):
				row["BelegDatum"] = belegdatum_dt
				return_list.append(row)
			
		return return_list

	def parse_string_to_float(self, input_string):
		clean_string = str(input_string)

		all_regex = "^\d+$"
		de_regex = "^\d+.\d+,\d{2}|\d+,\d{2}$"
		en_regex = "^\d+,\d+.\d{2}|\d+.\d{2}$"

		output_float = False

		if re.match(all_regex, clean_string):
			output_float = float(clean_string)

		elif re.match(de_regex, clean_string):
			#tausender Trennzeichen entfernen
			clean_string = clean_string.replace(".","")
			#Komma durch Punkt ersetzen
			clean_string = clean_string.replace(",",".")
			output_float = float(clean_string)
		elif re.match(en_regex, clean_string):
			#tausender Trennzeichen entfernen
			clean_string = clean_string.replace(",","")
			output_float = float(clean_string)

		return output_float
