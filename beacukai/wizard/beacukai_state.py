from openerp.osv import osv
from openerp.tools.translate import _
from openerp import netsvc
from openerp import pooler

class beacukai_confirm(osv.osv_memory):
	"""
	This wizard will confirm the all the selected draft invoices
	"""

	_name = "beacukai.confirm"
	_description = "Confirm the selected BCs"

	def beacukai_confirm(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		# pool_obj = pooler.get_pool(cr.dbname)
		data_bc = self.pool.get('beacukai.document').read(cr, uid, context['active_ids'], ['state'], context=context)

		for record in data_bc:
			if record['state'] not in ('draft'):
				raise osv.except_osv(_('Warning!'), _("Selected BC(s) cannot be confirmed as they are not in 'Draft' state."))
		
		self.pool.get('beacukai.document').action_done(cr, uid, context['active_ids'])
		return {'type': 'ir.actions.act_window_close'}

beacukai_confirm()

class beacukai_cancel(osv.osv_memory):
	"""
	This wizard will confirm the all the selected draft invoices
	"""

	_name = "beacukai.cancel"
	_description = "Cancel the selected BCs"

	def beacukai_cancel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		# pool_obj = pooler.get_pool(cr.dbname)
		data_bc = self.pool.get('beacukai.document').read(cr, uid, context['active_ids'], ['state'], context=context)

		for record in data_bc:
			if record['state'] not in ('draft','validated'):
				raise osv.except_osv(_('Warning!'), _("Selected BC(s) cannot be confirmed as they are not in 'Draft' or 'Valid BC' state."))
		
		self.pool.get('beacukai.document').action_cancel(cr, uid, context['active_ids'])
		return {'type': 'ir.actions.act_window_close'}

beacukai_cancel()

class beacukai_draft(osv.osv_memory):
	"""
	This wizard will confirm the all the selected draft invoices
	"""

	_name = "beacukai.draft"
	_description = "Set to Draft the selected BCs"

	def beacukai_set_draft(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		# pool_obj = pooler.get_pool(cr.dbname)
		data_bc = self.pool.get('beacukai.document').read(cr, uid, context['active_ids'], ['state'], context=context)

		for record in data_bc:
			if record['state'] not in ('cancelled'):
				raise osv.except_osv(_('Warning!'), _("Selected BC(s) cannot be confirmed as they are not in 'Cancelled' state."))
		
		self.pool.get('beacukai.document').action_set_draft(cr, uid, context['active_ids'])
		return {'type': 'ir.actions.act_window_close'}

beacukai_draft()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
