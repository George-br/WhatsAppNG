# -*- coding: UTF-8 -*-
import appModuleHandler
import api
import ui
import scriptHandler
import controlTypes
import config
import re
import addonHandler

try:
	from controlTypes import Role
except Exception:
	Role = None

# Initialize translation
addonHandler.initTranslation()

CONFIG_SECTION = "whatsappPhoneFilter"

# Configuration specification (required for NVDA to correctly read boolean values)
SPEC = {
	'filterChatList': 'boolean(default=False)',
	'filterMessageList': 'boolean(default=True)',
}

MAYBE_RE = re.compile(r"\bTalvez\b\s*", re.IGNORECASE)

# WhatsAppPlus regex: minimum 12 chars, lookahead to avoid matching time
PHONE_RE = re.compile(r"\+\d[()\d\s-]{8,15}(?=[^\d]|$|\s)")

class AppModule(appModuleHandler.AppModule):
	"""
	App Module for WhatsApp Desktop.
	Alt+1: Conversation list
	Alt+2: Message list
	"""

	scriptCategory = _("WhatsApp NG")

	def __init__(self, *args, **kwargs):
		super(AppModule, self).__init__(*args, **kwargs)

		# Register config spec (required for NVDA to correctly read boolean values)
		if CONFIG_SECTION not in config.conf:
			config.conf[CONFIG_SECTION] = {}
		config.conf.spec[CONFIG_SECTION] = SPEC

		self._toggling = False  # Flag to skip filter during focus changes

	def _shouldFilterChatList(self):
		"""Always read from config.conf and convert to boolean"""
		try:
			section = config.conf[CONFIG_SECTION]
			val = section.get("filterChatList", False)
			# Explicitly convert (may come as string from NVDA)
			if isinstance(val, str):
				val = val.lower() == 'true'
			return val
		except Exception:
			return False

	def _shouldFilterMessageList(self):
		"""Always read from config.conf and convert to boolean"""
		try:
			section = config.conf[CONFIG_SECTION]
			val = section.get("filterMessageList", True)
			# Explicitly convert (may come as string from NVDA)
			if isinstance(val, str):
				val = val.lower() == 'true'
			return val
		except Exception:
			return True

	@scriptHandler.script(
		description=_("Play voice message"),
		gesture="kb:enter"
	)
	def script_playAudio(self, gesture):
		"""Enter: Clicks first button of current message without moving focus."""
		try:
			# Only works in message list
			if not self._isMessageListFocus():
				gesture.send()
				return

			focus = api.getFocusObject()
			parent = getattr(focus, "parent", None)
			if not parent:
				gesture.send()
				return

			# Search for buttons in siblings
			siblings = getattr(parent, "children", [])
			for sibling in siblings:
				def find_buttons(obj):
					buttons = []
					if _role(obj) == controlTypes.Role.BUTTON:
						buttons.append(obj)
					for child in getattr(obj, "children", []):
						buttons.extend(find_buttons(child))
					return buttons

				buttons = find_buttons(sibling)
				if buttons:
					# 3 buttons = individual chat → button 0
					if len(buttons) == 3:
						buttons[0].doAction()
						return
					# 4 buttons = group or forwarded audio
					if len(buttons) == 4:
						states = getattr(buttons[1], "states", set())
						if 512 in states:  # HAS COLLAPSED = button 1 is menu → use button 0 (forwarded audio)
							buttons[0].doAction()
							return
						# No COLLAPSED = button 1 is play (group)
						buttons[1].doAction()
						return

		except Exception:
			gesture.send()

	@scriptHandler.script(
		description=_("Open context menu"),
		gesture="kb:shift+enter"
	)
	def script_contextMenu(self, gesture):
		"""Shift+Enter: Opens message context menu without moving focus."""
		try:
			# Only works in message list
			if not self._isMessageListFocus():
				return

			focus = api.getFocusObject()
			parent = getattr(focus, "parent", None)
			if not parent:
				return

			# Search for buttons in siblings
			siblings = getattr(parent, "children", [])

			for sibling in siblings:
				def find_buttons(obj):
					buttons = []
					if _role(obj) == controlTypes.Role.BUTTON:
						buttons.append(obj)
					for child in getattr(obj, "children", []):
						buttons.extend(find_buttons(child))
					return buttons

				buttons = find_buttons(sibling)
				if not buttons:
					continue

				# Search for button with COLLAPSED or use last one
				for btn in buttons:
					states = getattr(btn, "states", set())
					if 512 in states:  # COLLAPSED
						btn.doAction()
						return

				# Fallback: last button (menu)
				buttons[-1].doAction()
				return

		except Exception:
			pass

	@scriptHandler.script(
		description=_("Focus message composer"),
		gesture="kb:alt+d"
	)
	def script_focusComposer(self, gesture):
		"""Alt+D: Focuses message input field."""
		self._toggling = True
		try:
			focus = api.getFocusObject()
			ti = getattr(focus, "treeInterceptor", None)

			if not ti or not hasattr(ti, "rootNVDAObject"):
				ui.message(_("Message composer not found"))
				return

			root = ti.rootNVDAObject
			paths_to_try = [
				[0, 0, 0, 0, 3, 5, 0, 3, 0, 0, 0, 2, 0],
			]

			for path_indices in paths_to_try:
				try:
					obj = root
					valid_path = True

					for i in path_indices:
						children = getattr(obj, "children", []) or []
						if i < len(children):
							obj = children[i]
						else:
							valid_path = False
							break

					if valid_path:
						obj.setFocus()
						return

				except Exception:
					continue

			ui.message(_("Message composer not found"))
		except Exception:
			ui.message(_("Message composer not found"))
		finally:
			self._toggling = False

	def event_gainFocus(self, obj, nextHandler):
		"""Automatically activate focus mode in WhatsApp."""
		if obj.treeInterceptor:
			obj.treeInterceptor.passThrough = True
		nextHandler()

	def event_NVDAObject_init(self, obj):
		"""Filters phone numbers in object name before speaking (WhatsApp only)."""
		# Skip filtering if toggling (during Alt+1/Alt+2/Alt+D navigation)
		if self._toggling:
			return

		# Only process WhatsApp objects (check by appModule)
		try:
			app = getattr(obj, "appModule", None)
			if app and hasattr(app, "appName") and app.appName == "whatsapp.root":
				self._filterObjectName(obj)
		except Exception:
			pass

	def _filterObjectName(self, obj):
		"""Apply filters to object name (lightweight version for init)"""
		if not obj.name or self._toggling:
			return

		obj_role = _role(obj)

		# Check if has TABLE as ancestor up to 3 levels
		has_table_ancestor = self._hasAncestorWithRole(obj, ["TABLE"], limit=3)

		# SECTION WITHOUT TABLE ancestor = message list
		if obj_role == 86 and not has_table_ancestor:
			# Always filter "Talvez"
			obj.name = MAYBE_RE.sub("", obj.name)
			# Filter phones if toggle enabled
			if self._shouldFilterMessageList():
				obj.name = PHONE_RE.sub("", obj.name)

		# Any object WITH TABLE ancestor = conversation list
		elif has_table_ancestor:
			if self._shouldFilterChatList():
				obj.name = PHONE_RE.sub("", obj.name)

		# Remove extra spaces
		obj.name = re.sub(r"\s{2,}", " ", obj.name).strip()

	def _hasAncestorWithRole(self, obj, roleNames, limit=18):
		if Role is None:
			return False

		wanted = []
		for n in roleNames:
			if hasattr(Role, n):
				wanted.append(getattr(Role, n))

		for a in _get_ancestors(obj, limit=limit):
			if _role(a) in wanted:
				return True
		return False

	def _isConversationListFocus(self):
		try:
			focus = api.getFocusObject()
		except Exception:
			return False
		return self._hasAncestorWithRole(focus, ["TABLE"], limit=40)

	def _isMessageListFocus(self):
		try:
			focus = api.getFocusObject()
		except Exception:
			return False

		# The focus itself must be SECTION (not EDITABLETEXT inside SECTION)
		if _role(focus) != 86:
			return False

		# And does NOT have TABLE as ancestor
		return not self._hasAncestorWithRole(focus, ["TABLE"], limit=40)

	@scriptHandler.script(
		description=_("Go to WhatsApp conversation list"),
		gesture="kb:alt+1"
	)
	def script_goToConversationList(self, gesture):
		"""Alt+1: Go to WhatsApp conversation list."""
		self._toggling = True
		try:
			focus = api.getFocusObject()
			ti = getattr(focus, "treeInterceptor", None)

			if not ti or not hasattr(ti, "rootNVDAObject"):
				ui.message(_("Conversation list not found"))
				return

			root = ti.rootNVDAObject
			paths_to_try = [
				[0, 0, 0, 0, 3, 4, 1, 2, 0, 0, 0],
			]

			for path_indices in paths_to_try:
				try:
					obj = root
					valid_path = True

					for i in path_indices:
						children = getattr(obj, "children", []) or []
						if i < len(children):
							obj = children[i]
						else:
							valid_path = False
							break

					if valid_path and _role(obj) == 28:
						def find_first_cell(o, depth=0):
							if depth > 3:
								return None
							try:
								if _role(o) == 29:
									return o
								for c in getattr(o, "children", []):
									f = find_first_cell(c, depth + 1)
									if f:
										return f
							except:
								pass
							return None

						cell = find_first_cell(obj)
						if cell:
							cell.setFocus()
							return
						else:
							obj.setFocus()
							return

				except Exception:
					continue

			ui.message(_("Conversation list not found"))
		except Exception:
			ui.message(_("Conversation list not found"))
		finally:
			self._toggling = False

	@scriptHandler.script(
		description=_("Go to WhatsApp message list"),
		gesture="kb:alt+2"
	)
	def script_goToMessageList(self, gesture):
		"""Alt+2: Go to WhatsApp message list."""
		self._toggling = True
		try:
			ti = getattr(api.getFocusObject(), "treeInterceptor", None)

			if not ti or not hasattr(ti, "rootNVDAObject"):
				ui.message(_("Message list not found"))
				return

			root = ti.rootNVDAObject
			paths_to_try = [
				[0, 0, 0, 0, 3, 5, 0, 2, 2, 0],
				[0, 0, 0, 0, 3, 5, 0, 2, 1, 0],
				[0, 0, 0, 0, 3, 5, 0, 2, 2, 0, 9],
				[0, 0, 0, 0, 3, 5, 0, 2, 1, 0, 9],
				[0, 0, 0, 0, 3, 5, 0, 2, 1, 1],
				[0, 0, 0, 0, 3, 5, 0, 2, 2, 1],
			]

			for path_indices in paths_to_try:
				try:
					obj = root
					valid_path = True

					for i in path_indices:
						children = getattr(obj, "children", []) or []
						if i < len(children):
							obj = children[i]
						else:
							valid_path = False
							break

					if not valid_path:
						continue

					# Try to focus
					obj.setFocus()
					return

				except Exception:
					continue

			ui.message(_("Message list not found"))
		except Exception:
			ui.message(_("Message list not found"))
		finally:
			self._toggling = False

	@scriptHandler.script(
		description=_("Toggle phone number filtering in conversation list")
	)
	def script_togglePhoneReadingInChatList(self, gesture):
		"""Toggle phone number reading in conversation list."""
		try:
			if not self._isConversationListFocus():
				ui.message(_("Use this command in the conversation list"))
				return

			current = self._shouldFilterChatList()
			new_val = not current
			config.conf[CONFIG_SECTION]["filterChatList"] = new_val
			config.conf.save()

			if new_val:
				ui.message(_("Conversation list: phone numbers hidden"))
			else:
				ui.message(_("Conversation list: phone numbers visible"))
		except Exception:
			pass

	@scriptHandler.script(
		description=_("Toggle phone number filtering in message list")
	)
	def script_togglePhoneReadingInMessageList(self, gesture):
		"""Toggle phone number reading in message list."""
		try:
			if not self._isMessageListFocus():
				ui.message(_("Use this command in the message list"))
				return

			current = self._shouldFilterMessageList()
			new_val = not current
			config.conf[CONFIG_SECTION]["filterMessageList"] = new_val
			config.conf.save()

			if new_val:
				ui.message(_("Message list: phone numbers hidden"))
			else:
				ui.message(_("Message list: phone numbers visible"))
		except Exception:
			pass

def _role(obj):
	try:
		return obj.role
	except Exception:
		return None

def _get_ancestors(obj, limit=40):
	cur = obj
	out = []
	for _ in range(limit):
		try:
			cur = cur.parent
		except Exception:
			break
		if not cur:
			break
		out.append(cur)
	return out
