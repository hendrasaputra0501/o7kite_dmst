from datetime import datetime
from lxml import etree
import math
import pytz
import re

import openerp
import decimal_precision as dp
from openerp import SUPERUSER_ID
from openerp import pooler, tools
from openerp.osv import osv, fields
from openerp.osv.expression import get_unaccent_wrapper
from openerp.tools.translate import _
from openerp.tools.yaml_import import is_comment

class res_partner(osv.Model):
	_inherit = "res.partner"

	_columns = {
		'partner_code' : fields.char('Partner Code'),
		'default_currency_id' : fields.many2one('res.currency','Default Currency'),
	}

	_defaults = {
		'partner_code' : lambda *p:'/',
	}

	def name_get(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		if isinstance(ids, (int, long)):
			ids = [ids]
		res = []
		for record in self.browse(cr, uid, ids, context=context):
			name = record.name
			if record.partner_code:
				name = "[%s] %s"%(record.partner_code, name)
			if record.parent_id and not record.is_company:
				name = "%s, %s" % (record.parent_name, name)
			if context.get('show_address'):
				name = name + "\n" + self._display_address(cr, uid, record, without_company=True, context=context)
				name = name.replace('\n\n','\n')
				name = name.replace('\n\n','\n')
			if context.get('show_email') and record.email:
				name = "%s <%s>" % (name, record.email)
			res.append((record.id, name))
		return res

	def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
		if not args:
			args = []
		if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):

			self.check_access_rights(cr, uid, 'read')
			where_query = self._where_calc(cr, uid, args, context=context)
			self._apply_ir_rules(cr, uid, where_query, 'read', context=context)
			from_clause, where_clause, where_clause_params = where_query.get_sql()
			where_str = where_clause and (" WHERE %s AND " % where_clause) or ' WHERE '

			# search on the name of the contacts and of its company
			search_name = name
			if operator in ('ilike', 'like'):
				search_name = '%%%s%%' % name
			if operator in ('=ilike', '=like'):
				operator = operator[1:]

			unaccent = get_unaccent_wrapper(cr)

			# TODO: simplify this in trunk with `display_name`, once it is stored
			# Perf note: a CTE expression (WITH ...) seems to have an even higher cost
			#            than this query with duplicated CASE expressions. The bulk of
			#            the cost is the ORDER BY, and it is inevitable if we want
			#            relevant results for the next step, otherwise we'd return
			#            a random selection of `limit` results.

			display_name = """CASE WHEN company.id IS NULL OR res_partner.is_company
								   THEN {partner_name}
								   ELSE {company_name} || ', ' || {partner_name}
							   END""".format(partner_name=unaccent('res_partner.name'),
											 company_name=unaccent('company.name'))
			partner_code = """res_partner.partner_code"""

			query = """SELECT res_partner.id
						 FROM res_partner
					LEFT JOIN res_partner company
						   ON res_partner.parent_id = company.id
					  {where} ({email} {operator} {percent}
						   OR {display_name} {operator} {percent}
						   OR {partner_code} {operator} {percent})
					 ORDER BY {display_name}
					""".format(where=where_str, operator=operator,
							   email=unaccent('res_partner.email'),
							   percent=unaccent('%s'),
							   display_name=display_name,
							   partner_code=partner_code,)

			where_clause_params += [search_name, search_name, search_name]
			if limit:
				query += ' limit %s'
				where_clause_params.append(limit)
			cr.execute(query, where_clause_params)
			ids = map(lambda x: x[0], cr.fetchall())

			if ids:
				return self.name_get(cr, uid, ids, context)
			else:
				return []
		return super(res_partner,self).name_search(cr, uid, name, args, operator=operator, context=context, limit=limit)

	def create(self, cr, user, vals, context=None):
		if context is None:
			context = {}
		user_data = self.pool.get('res.users').browse(cr,user,user)
		company_id = user_data.company_id or False 
		if ('partner_code' not in vals) or (vals.get('partner_code')=='/'):
			seq_obj_name =  self._inherit
			if vals.get('customer',False)==True and vals.get('supplier',False)==False:
				partner_type = '.customer'
			elif vals.get('customer',False)==False and vals.get('supplier',False)==True:
				partner_type = '.supplier'
			else:
				partner_type = '.other'
			
			vals['partner_code'] = self.pool.get('ir.sequence').get(cr, user, seq_obj_name+partner_type)
		res = super(res_partner, self).create(cr, user, vals, context)
		return res