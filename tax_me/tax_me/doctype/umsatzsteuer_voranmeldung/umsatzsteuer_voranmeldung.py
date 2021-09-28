# -*- coding: utf-8 -*-
# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from os import umask
import frappe
from frappe.model.document import Document
from datetime import datetime as dt
import io
from frappe.utils.file_manager import save_file
from frappe.utils import password
from frappe.utils.data import encode
import pymssql
import re

class UmsatzsteuerVoranmeldung(Document):
	#Regex für das Prüfen auf plausibles Datum
	epic_date_regex = r"^(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})$"

	@frappe.whitelist()
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
		for pi in pi_list:
			print(str(pi["BelegDatum"]) + " - " + pi["BelegNummer"])

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
					except:
						frappe.throw("Datum in Beleg kann nicht interpretiert werden. Bitte den Beleg in Inoxision korrigieren:<br>" + str(row))
			#print(belegdatum_dt)

			#Datum Prüfen, wir geben nur Belege innerhalb des gewählten Zeitraums zurück
			if belegdatum_dt >= dt.fromisoformat(self.von) and belegdatum_dt <= dt.fromisoformat(self.bis):
				row["BelegDatum"] = belegdatum_dt
				return_list.append(row)
			
		return return_list
	
	@frappe.whitelist()
	def daten_generieren(self):
		von_datum_dt = dt.strptime (self.von,"%Y-%m-%d")
		von_datum = dt.strftime(von_datum_dt, "%Y%m%d")
		bis_datum_dt = dt.strptime (self.bis,"%Y-%m-%d")
		bis_datum = dt.strftime(bis_datum_dt, "%Y%m%d")
		rechnungsdaten = "EXTF;510;21;Buchungsstapel;7;2,02E+16;;RE;;0084947SOL0000000022;84947;11155;"+von_datum+";4;"+von_datum+";"+bis_datum+"\n"+"Umsatz (ohne Soll/Haben-Kz);Soll/Haben-Kennzeichen;WKZ Umsatz;Kurs;Basis-Umsatz;WKZ Basis-Umsatz;Konto;Gegenkonto (ohne BU-Schlüssel);BU-Schlüssel;Belegdatum;Belegfeld 1;Belegfeld 2;Skonto;Buchungstext;;\n"
		si_list = frappe.get_all(
					"Sales Invoice", 
					filters={
						"docstatus": 1,
						"posting_date": ["between", [self.von, self.bis]]
						},
					fields = ["name", "posting_date", "total", "is_return", "customer"]
					)
		for si in si_list:
			if si ["is_return"] == 1:
				soll_haben = "H"
				buchungstext = "Rechnungskorrektur"
			else:
				soll_haben = "S"
				buchungstext = "Rechnung"
			
			account = frappe.get_all("Party Account", filters={ "parent" : si["customer"]})
			if len(account) ==1:
				account_doc = frappe.get_doc("Party Account",account[0]["name"])
			
				konto = account_doc.debtor_creditor_number
			umsatz = ("%.1f" % si["total"]).replace(".",",")
			belegdatum_dt = dt.strptime (str(si["posting_date"]),"%Y-%m-%d")
			belegdatum = dt.strftime(belegdatum_dt, "%d%m")
			belegfeld1 = str(si["name"].split("-")[1])
			
			zeile = umsatz+";"+ soll_haben+";;;;;"+str(konto)+";4400;0;"+ belegdatum +";" + belegfeld1 + ";;;" + buchungstext +";;\n"
			rechnungsdaten += zeile
		print(rechnungsdaten)
		b = io.BytesIO(rechnungsdaten.encode())
		save_file("Ausgangsrechnungen_itsdave_gmbh.xlsx", b.read(),"Umsatzsteuer Voranmeldung",None,False,1)
		# frappe.response["filename"] = "Ausgangsrechnungen_itsdave_gmbh.csv"
		# frappe.response["filecontent"] = io_objekt
		# frappe.response["type"] = "binary"



