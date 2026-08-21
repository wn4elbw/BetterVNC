/*
 * webvnc: HTML5 VNC client
 * Copyright (C) 2019 The noVNC authors
 * Licensed under MPL 2.0 (see LICENSE.txt)
 *
 * See README.md for usage and integration instructions.
 */

import * as Log from '../core/util/logging.js';
import _, { l10n } from './localization.js';
import { isTouchDevice, isMac, isIOS, isAndroid, isChromeOS, isSafari,
         hasScrollbarGutter, dragThreshold, browserAsyncClipboardSupport }
    from '../core/util/browser.js';
import { setCapture, getPointerEvent } from '../core/util/events.js';
import KeyTable from "../core/input/keysym.js";
import keysyms from "../core/input/keysymdef.js";
import Keyboard from "../core/input/keyboard.js";
import RFB from "../core/rfb.js";
import WakeLockManager from './wakelock.js';
import * as WebUtil from "./webutil.js";

const PAGE_TITLE = "BetterVNC";

const LINGUAS = ["cs", "de", "el", "es", "fr", "hr", "hu", "it", "ja", "ko", "nl", "pl", "pt_BR", "ru", "sv", "tr", "uk", "zh_CN", "zh_TW"];

const UI = {

    customSettings: {},

    connected: false,
    desktopName: "",

    statusTimeout: null,
    hideKeyboardTimeout: null,
    idleControlbarTimeout: null,
    closeControlbarTimeout: null,

    controlbarGrabbed: false,
    controlbarDrag: false,
    controlbarMouseDownClientX: 0,
    controlbarMouseDownOffsetX: 0,
    controlbarMouseDownClientY: 0,
    controlbarMouseDownOffsetY: 0,

    lastKeyboardinput: null,
    defaultKeyboardinputLen: 100,

    inhibitReconnect: true,
    reconnectCallback: null,
    reconnectPassword: null,

    wakeLockManager: new WakeLockManager(),

    async start(options={}) {
        UI.customSettings = options.settings || {};
        if (UI.customSettings.defaults === undefined) {
            UI.customSettings.defaults = {};
        }
        if (UI.customSettings.mandatory === undefined) {
            UI.customSettings.mandatory = {};
        }

        // Set up translations
        try {
            await l10n.setup(LINGUAS, "app/locale/");
        } catch (err) {
            Log.Error("Failed to load translations: " + err);
        }

        // Initialize setting storage
        await WebUtil.initSettings();

        // Wait for the page to load
        if (document.readyState !== "interactive" && document.readyState !== "complete") {
            await new Promise((resolve, reject) => {
                document.addEventListener('DOMContentLoaded', resolve);
            });
        }

        UI.initSettings();

        // Translate the DOM
        l10n.translateDOM();

        // We rely on modern APIs which might not be available in an
        // insecure context
        if (!window.isSecureContext) {
            // FIXME: This gets hidden when connecting
            UI.showStatus(_("Running without HTTPS is not recommended, crashes or other issues are likely."), 'error');
        }

        // Try to fetch version number
        try {
            let response = await fetch('./package.json');
            if (!response.ok) {
                throw Error("" + response.status + " " + response.statusText);
            }

            let packageInfo = await response.json();
            Array.from(document.getElementsByClassName('webvnc_version')).forEach(el => el.innerText = packageInfo.version);
        } catch (err) {
            Log.Error("Couldn't fetch package.json: " + err);
            Array.from(document.getElementsByClassName('webvnc_version_wrapper'))
                .concat(Array.from(document.getElementsByClassName('webvnc_version_separator')))
                .forEach(el => el.style.display = 'none');
        }

        // Adapt the interface for touch screen devices
        if (isTouchDevice) {
            // Remove the address bar
            setTimeout(() => window.scrollTo(0, 1), 100);
        }

        // Restore control bar position
        const pos = WebUtil.readSetting('controlbar_pos');
        if (['left', 'right', 'top', 'bottom'].includes(pos)) {
            UI.toggleControlbarSide(pos);
        } else {
            UI.toggleControlbarSide('left');
        }

        UI.initFullscreen();

        // Setup event handlers
        UI.addControlbarHandlers();
        UI.addTouchSpecificHandlers();
        UI.addExtraKeysHandlers();
        UI.addMachineHandlers();
        UI.addConnectionControlHandlers();
        UI.addClipboardHandlers();
        UI.addSettingsHandlers();
        document.getElementById("webvnc_status")
            .addEventListener('click', UI.hideStatus);

        // Bootstrap fallback input handler
        UI.keyboardinputReset();

        UI.openControlbar();

        UI.updateVisualState('init');

        document.documentElement.classList.remove("webvnc_loading");

        // Always connect automatically since the connect panel has been removed
        UI.connect();
    },

    initFullscreen() {
        // Only show the button if fullscreen is properly supported
        // * Safari doesn't support alphanumerical input while in fullscreen
        if (!isSafari() &&
            (document.documentElement.requestFullscreen ||
             document.documentElement.mozRequestFullScreen ||
             document.documentElement.webkitRequestFullscreen ||
             document.body.msRequestFullscreen)) {
            document.getElementById('webvnc_fullscreen_button')
                .classList.remove("webvnc_hidden");
            UI.addFullscreenHandlers();
        }
    },

    initSettings() {
        // Logging selection dropdown
        const llevels = ['error', 'warn', 'info', 'debug'];
        for (let i = 0; i < llevels.length; i += 1) {
            UI.addOption(document.getElementById('webvnc_setting_logging'), llevels[i], llevels[i]);
        }

        // Settings with immediate effects
        UI.initSetting('logging', 'warn');
        UI.updateLogging();

        UI.setupSettingLabels();

        /* Populate the controls if defaults are provided in the URL */
        UI.initSetting('host', '');
        UI.initSetting('port', 0);
        UI.initSetting('encrypt', (window.location.protocol === "https:"));
        UI.initSetting('password');
        UI.initSetting('autoconnect', false);
        UI.initSetting('view_clip', false);
        UI.initSetting('resize', 'off');
        UI.initSetting('quality', 6);
        UI.initSetting('compression', 2);
        UI.initSetting('shared', true);
        UI.initSetting('bell', 'on');
        UI.initSetting('view_only', false);
        UI.initSetting('show_dot', false);
        UI.initSetting('path', 'websockify');
        UI.initSetting('repeaterID', '');
        UI.initSetting('reconnect', false);
        UI.initSetting('reconnect_delay', 5000);
        UI.initSetting('keep_device_awake', false);
    },
    // Adds a link to the label elements on the corresponding input elements
    setupSettingLabels() {
        const labels = document.getElementsByTagName('LABEL');
        for (let i = 0; i < labels.length; i++) {
            const htmlFor = labels[i].htmlFor;
            if (htmlFor != '') {
                const elem = document.getElementById(htmlFor);
                if (elem) elem.label = labels[i];
            } else {
                // If 'for' isn't set, use the first input element child
                const children = labels[i].children;
                for (let j = 0; j < children.length; j++) {
                    if (children[j].form !== undefined) {
                        children[j].label = labels[i];
                        break;
                    }
                }
            }
        }
    },

/* ------^-------
*     /INIT
* ==============
* EVENT HANDLERS
* ------v------*/

    addControlbarHandlers() {
        document.getElementById("webvnc_control_bar")
            .addEventListener('mousemove', UI.activateControlbar);
        document.getElementById("webvnc_control_bar")
            .addEventListener('mouseup', UI.activateControlbar);
        document.getElementById("webvnc_control_bar")
            .addEventListener('mousedown', UI.activateControlbar);
        document.getElementById("webvnc_control_bar")
            .addEventListener('keydown', UI.activateControlbar);

        document.getElementById("webvnc_control_bar")
            .addEventListener('mousedown', UI.keepControlbar);
        document.getElementById("webvnc_control_bar")
            .addEventListener('keydown', UI.keepControlbar);

        document.getElementById("webvnc_view_drag_button")
            .addEventListener('click', UI.toggleViewDrag);

        document.getElementById("webvnc_control_bar_handle")
            .addEventListener('mousedown', UI.controlbarHandleMouseDown);
        document.getElementById("webvnc_control_bar_handle")
            .addEventListener('mouseup', UI.controlbarHandleMouseUp);
        document.getElementById("webvnc_control_bar_handle")
            .addEventListener('mousemove', UI.dragControlbarHandle);
        // resize events aren't available for elements
        window.addEventListener('resize', UI.updateControlbarHandle);

        const exps = document.getElementsByClassName("webvnc_expander");
        for (let i = 0;i < exps.length;i++) {
            exps[i].addEventListener('click', UI.toggleExpander);
        }
    },

    addTouchSpecificHandlers() {
        document.getElementById("webvnc_keyboard_button")
            .addEventListener('click', UI.toggleVirtualKeyboard);

        UI.touchKeyboard = new Keyboard(document.getElementById('webvnc_keyboardinput'));
        UI.touchKeyboard.onkeyevent = UI.keyEvent;
        UI.touchKeyboard.grab();
        document.getElementById("webvnc_keyboardinput")
            .addEventListener('input', UI.keyInput);
        document.getElementById("webvnc_keyboardinput")
            .addEventListener('focus', UI.onfocusVirtualKeyboard);
        document.getElementById("webvnc_keyboardinput")
            .addEventListener('blur', UI.onblurVirtualKeyboard);
        document.getElementById("webvnc_keyboardinput")
            .addEventListener('submit', () => false);

        document.documentElement
            .addEventListener('mousedown', UI.keepVirtualKeyboard, true);

        document.getElementById("webvnc_control_bar")
            .addEventListener('touchstart', UI.activateControlbar);
        document.getElementById("webvnc_control_bar")
            .addEventListener('touchmove', UI.activateControlbar);
        document.getElementById("webvnc_control_bar")
            .addEventListener('touchend', UI.activateControlbar);
        document.getElementById("webvnc_control_bar")
            .addEventListener('input', UI.activateControlbar);

        document.getElementById("webvnc_control_bar")
            .addEventListener('touchstart', UI.keepControlbar);
        document.getElementById("webvnc_control_bar")
            .addEventListener('input', UI.keepControlbar);

        document.getElementById("webvnc_control_bar_handle")
            .addEventListener('touchstart', UI.controlbarHandleMouseDown);
        document.getElementById("webvnc_control_bar_handle")
            .addEventListener('touchend', UI.controlbarHandleMouseUp);
        document.getElementById("webvnc_control_bar_handle")
            .addEventListener('touchmove', UI.dragControlbarHandle);
    },

    addExtraKeysHandlers() {
        document.getElementById("webvnc_toggle_extra_keys_button")
            .addEventListener('click', UI.toggleExtraKeys);
        document.getElementById("webvnc_toggle_ctrl_button")
            .addEventListener('click', UI.toggleCtrl);
        document.getElementById("webvnc_toggle_windows_button")
            .addEventListener('click', UI.toggleWindows);
        document.getElementById("webvnc_toggle_alt_button")
            .addEventListener('click', UI.toggleAlt);
        document.getElementById("webvnc_send_tab_button")
            .addEventListener('click', UI.sendTab);
        document.getElementById("webvnc_send_esc_button")
            .addEventListener('click', UI.sendEsc);
        document.getElementById("webvnc_send_ctrl_alt_del_button")
            .addEventListener('click', UI.sendCtrlAltDel);
    },

    addMachineHandlers() {
        document.getElementById("webvnc_shutdown_button")
            .addEventListener('click', () => UI.rfb.machineShutdown());
        document.getElementById("webvnc_reboot_button")
            .addEventListener('click', () => UI.rfb.machineReboot());
        document.getElementById("webvnc_reset_button")
            .addEventListener('click', () => UI.rfb.machineReset());
        document.getElementById("webvnc_power_button")
            .addEventListener('click', UI.togglePowerPanel);
    },

    addConnectionControlHandlers() {
        document.getElementById("webvnc_disconnect_button")
            .addEventListener('click', UI.disconnect);
        document.getElementById("webvnc_cancel_reconnect_button")
            .addEventListener('click', UI.cancelReconnect);

        document.getElementById("webvnc_approve_server_button")
            .addEventListener('click', UI.approveServer);
        document.getElementById("webvnc_reject_server_button")
            .addEventListener('click', UI.rejectServer);
        document.getElementById("webvnc_credentials_button")
            .addEventListener('click', UI.setCredentials);
    },

    addClipboardHandlers() {
        document.getElementById("webvnc_clipboard_button")
            .addEventListener('click', UI.toggleClipboardPanel);
        document.getElementById("webvnc_clipboard_text")
            .addEventListener('change', UI.clipboardSend);
    },

    // Add a call to save settings when the element changes,
    // unless the optional parameter changeFunc is used instead.
    addSettingChangeHandler(name, changeFunc) {
        const settingElem = document.getElementById("webvnc_setting_" + name);
        if (changeFunc === undefined) {
            changeFunc = () => UI.saveSetting(name);
        }
        settingElem.addEventListener('change', changeFunc);
    },

    addSettingsHandlers() {
        document.getElementById("webvnc_settings_button")
            .addEventListener('click', UI.toggleSettingsPanel);

        UI.addSettingChangeHandler('encrypt');
        UI.addSettingChangeHandler('resize');
        UI.addSettingChangeHandler('resize', UI.applyResizeMode);
        UI.addSettingChangeHandler('resize', UI.updateViewClip);
        UI.addSettingChangeHandler('quality');
        UI.addSettingChangeHandler('quality', UI.updateQuality);
        UI.addSettingChangeHandler('compression');
        UI.addSettingChangeHandler('compression', UI.updateCompression);
        UI.addSettingChangeHandler('view_clip');
        UI.addSettingChangeHandler('view_clip', UI.updateViewClip);
        UI.addSettingChangeHandler('shared');
        UI.addSettingChangeHandler('view_only');
        UI.addSettingChangeHandler('view_only', UI.updateViewOnly);
        UI.addSettingChangeHandler('show_dot');
        UI.addSettingChangeHandler('show_dot', UI.updateShowDotCursor);
        UI.addSettingChangeHandler('keep_device_awake');
        UI.addSettingChangeHandler('keep_device_awake', UI.updateRequestWakelock);
        UI.addSettingChangeHandler('host');
        UI.addSettingChangeHandler('port');
        UI.addSettingChangeHandler('path');
        UI.addSettingChangeHandler('repeaterID');
        UI.addSettingChangeHandler('logging');
        UI.addSettingChangeHandler('logging', UI.updateLogging);
        UI.addSettingChangeHandler('reconnect');
        UI.addSettingChangeHandler('reconnect_delay');
    },

    addFullscreenHandlers() {
        document.getElementById("webvnc_fullscreen_button")
            .addEventListener('click', UI.toggleFullscreen);

        window.addEventListener('fullscreenchange', UI.updateFullscreenButton);
        window.addEventListener('mozfullscreenchange', UI.updateFullscreenButton);
        window.addEventListener('webkitfullscreenchange', UI.updateFullscreenButton);
        window.addEventListener('msfullscreenchange', UI.updateFullscreenButton);
    },

/* ------^-------
 * /EVENT HANDLERS
 * ==============
 *     VISUAL
 * ------v------*/

    // Disable/enable controls depending on connection state
    updateVisualState(state) {

        document.documentElement.classList.remove("webvnc_connecting");
        document.documentElement.classList.remove("webvnc_connected");
        document.documentElement.classList.remove("webvnc_disconnecting");
        document.documentElement.classList.remove("webvnc_reconnecting");

        const transitionElem = document.getElementById("webvnc_transition_text");
        switch (state) {
            case 'init':
                break;
            case 'connecting':
                transitionElem.textContent = _("Connecting...");
                document.documentElement.classList.add("webvnc_connecting");
                break;
            case 'connected':
                document.documentElement.classList.add("webvnc_connected");
                break;
            case 'disconnecting':
                transitionElem.textContent = _("Disconnecting...");
                document.documentElement.classList.add("webvnc_disconnecting");
                break;
            case 'disconnected':
                break;
            case 'reconnecting':
                transitionElem.textContent = _("Reconnecting...");
                document.documentElement.classList.add("webvnc_reconnecting");
                break;
            default:
                Log.Error("Invalid visual state: " + state);
                UI.showStatus(_("Internal error"), 'error');
                return;
        }

        if (UI.connected) {
            UI.updateViewClip();

            UI.disableSetting('encrypt');
            UI.disableSetting('shared');
            UI.disableSetting('host');
            UI.disableSetting('port');
            UI.disableSetting('path');
            UI.disableSetting('repeaterID');

            // Hide the controlbar after 2 seconds
            UI.closeControlbarTimeout = setTimeout(UI.closeControlbar, 2000);
        } else {
            UI.enableSetting('encrypt');
            UI.enableSetting('shared');
            UI.enableSetting('host');
            UI.enableSetting('port');
            UI.enableSetting('path');
            UI.enableSetting('repeaterID');
            UI.updatePowerButton();
            UI.keepControlbar();
        }

        // State change closes dialogs as they may not be relevant
        // anymore
        UI.closeAllPanels();
        document.getElementById('webvnc_verify_server_dlg')
            .classList.remove('webvnc_open');
        document.getElementById('webvnc_credentials_dlg')
            .classList.remove('webvnc_open');
    },

    showStatus(text, statusType, time) {
        const statusElem = document.getElementById('webvnc_status');

        if (typeof statusType === 'undefined') {
            statusType = 'normal';
        }

        // Don't overwrite more severe visible statuses and never
        // errors. Only shows the first error.
        if (statusElem.classList.contains("webvnc_open")) {
            if (statusElem.classList.contains("webvnc_status_error")) {
                return;
            }
            if (statusElem.classList.contains("webvnc_status_warn") &&
                statusType === 'normal') {
                return;
            }
        }

        clearTimeout(UI.statusTimeout);

        switch (statusType) {
            case 'error':
                statusElem.classList.remove("webvnc_status_warn");
                statusElem.classList.remove("webvnc_status_normal");
                statusElem.classList.add("webvnc_status_error");
                break;
            case 'warning':
            case 'warn':
                statusElem.classList.remove("webvnc_status_error");
                statusElem.classList.remove("webvnc_status_normal");
                statusElem.classList.add("webvnc_status_warn");
                break;
            case 'normal':
            case 'info':
            default:
                statusElem.classList.remove("webvnc_status_error");
                statusElem.classList.remove("webvnc_status_warn");
                statusElem.classList.add("webvnc_status_normal");
                break;
        }

        statusElem.textContent = text;
        statusElem.classList.add("webvnc_open");

        // If no time was specified, show the status for 1.5 seconds
        if (typeof time === 'undefined') {
            time = 1500;
        }

        // Error messages do not timeout
        if (statusType !== 'error') {
            UI.statusTimeout = window.setTimeout(UI.hideStatus, time);
        }
    },

    hideStatus() {
        clearTimeout(UI.statusTimeout);
        document.getElementById('webvnc_status').classList.remove("webvnc_open");
    },

    activateControlbar(event) {
        clearTimeout(UI.idleControlbarTimeout);
        // We manipulate the anchor instead of the actual control
        // bar in order to avoid creating new a stacking group
        document.getElementById('webvnc_control_bar_anchor')
            .classList.remove("webvnc_idle");
        UI.idleControlbarTimeout = window.setTimeout(UI.idleControlbar, 2000);
    },

    idleControlbar() {
        // Don't fade if a child of the control bar has focus
        if (document.getElementById('webvnc_control_bar')
            .contains(document.activeElement) && document.hasFocus()) {
            UI.activateControlbar();
            return;
        }

        document.getElementById('webvnc_control_bar_anchor')
            .classList.add("webvnc_idle");
    },

    keepControlbar() {
        clearTimeout(UI.closeControlbarTimeout);
    },

    openControlbar() {
        document.getElementById('webvnc_control_bar')
            .classList.add("webvnc_open");
    },

    closeControlbar() {
        UI.closeAllPanels();
        document.getElementById('webvnc_control_bar')
            .classList.remove("webvnc_open");
        UI.rfb.focus();
    },

    toggleControlbar() {
        if (document.getElementById('webvnc_control_bar')
            .classList.contains("webvnc_open")) {
            UI.closeControlbar();
        } else {
            UI.openControlbar();
        }
    },

    getControlbarPos() {
        const anchor = document.getElementById('webvnc_control_bar_anchor');
        if (anchor.classList.contains('webvnc_right')) return 'right';
        if (anchor.classList.contains('webvnc_top')) return 'top';
        if (anchor.classList.contains('webvnc_bottom')) return 'bottom';
        return 'left';
    },

    toggleControlbarSide(pos) {
        // Temporarily disable animation, if bar is displayed, to avoid weird
        // movement. The transitionend-event will not fire when display=none.
        const bar = document.getElementById('webvnc_control_bar');
        const barDisplayStyle = window.getComputedStyle(bar).display;
        if (barDisplayStyle !== 'none') {
            bar.style.transitionDuration = '0s';
            bar.addEventListener('transitionend', () => bar.style.transitionDuration = '');
        }

        const anchor = document.getElementById('webvnc_control_bar_anchor');

        anchor.classList.remove('webvnc_right', 'webvnc_top', 'webvnc_bottom');
        if (['right', 'top', 'bottom'].includes(pos)) {
            anchor.classList.add(`webvnc_${pos}`);
        }
        WebUtil.writeSetting('controlbar_pos', pos);

        // Consider this a movement of the handle
        UI.controlbarDrag = true;

        // The user has "followed" hint, let's hide it until the next drag
        UI.showControlbarHint(false, false);
    },

    showControlbarHint(show, animate=true) {
        const getPos = element =>
            ['right', 'top', 'bottom'].find(pos =>
                element.classList.contains(`webvnc_${pos}`)
            ) ?? 'left';

        const anchor = document.getElementById('webvnc_control_bar_anchor');
        const anchorPos = getPos(anchor);

        document.querySelectorAll('.webvnc_control_bar_hint').forEach((hint) => {
            const hintPos = getPos(hint.parentElement);
            const shouldShow = show && (hintPos !== anchorPos);

            hint.classList.toggle('webvnc_active', shouldShow);
            hint.classList.toggle('webvnc_notransition', !animate || !shouldShow);
        });
    },

    dragControlbarHandle(e) {
        if (!UI.controlbarGrabbed) return;

        const ptr = getPointerEvent(e);

        let controlBarPos = UI.getControlbarPos();

        if (ptr.clientX < (window.innerWidth * 0.1) &&
            ptr.clientY > (window.innerHeight * 0.25) &&
            ptr.clientY < (window.innerHeight * 0.75)) {
            if (controlBarPos !== 'left') {
                UI.toggleControlbarSide('left');
                controlBarPos = 'left';
            }

        } else if (ptr.clientX > (window.innerWidth * 0.9) &&
                   ptr.clientY > (window.innerHeight * 0.25) &&
                   ptr.clientY < (window.innerHeight * 0.75)) {
            if (controlBarPos !== 'right') {
                UI.toggleControlbarSide('right');
                controlBarPos = 'right';
            }

        // Slightly increased height thresholds since 10% of the
        // height proved small in practice
        } else if (ptr.clientX > (window.innerWidth * 0.25) &&
                   ptr.clientX < (window.innerWidth * 0.75) &&
                   ptr.clientY < (window.innerHeight * 0.2)) {
            if (controlBarPos !== 'top') {
                UI.toggleControlbarSide('top');
                controlBarPos = 'top';
            }

        } else if (ptr.clientX > (window.innerWidth * 0.25) &&
                   ptr.clientX < (window.innerWidth * 0.75) &&
                   ptr.clientY > (window.innerHeight * 0.8)) {
            if (controlBarPos !== 'bottom') {
                UI.toggleControlbarSide("bottom");
                controlBarPos = 'bottom';
            }
        }

        const isVertical = controlBarPos === 'left' || controlBarPos === 'right';

        if (!UI.controlbarDrag) {
            const dragDistance = isVertical
                ? Math.abs(ptr.clientY - UI.controlbarMouseDownClientY)
                : Math.abs(ptr.clientX - UI.controlbarMouseDownClientX);

            if (dragDistance < dragThreshold) return;

            UI.controlbarDrag = true;
        }

        if (isVertical) {
            const eventY = ptr.clientY - UI.controlbarMouseDownOffsetY;
            UI.moveControlbarHandle(eventY, true);
        } else {
            const eventX = ptr.clientX - UI.controlbarMouseDownOffsetX;
            UI.moveControlbarHandle(eventX, false);
        }

        e.preventDefault();
        e.stopPropagation();
        UI.keepControlbar();
        UI.activateControlbar();
    },

    // Move the handle but don't allow any position outside the bounds
    moveControlbarHandle(viewportRelativeCoord, isVertical) {
        const handle = document.getElementById("webvnc_control_bar_handle");

        const handleSpan = isVertical
            ? handle.getBoundingClientRect().height
            : handle.getBoundingClientRect().width;

        const controlbarBounds = document.getElementById("webvnc_control_bar")
            .getBoundingClientRect();
        const controlbarBoundsStart = isVertical
            ? controlbarBounds.top
            : controlbarBounds.left;
        const controlbarBoundsSpan  = isVertical
            ? controlbarBounds.height
            : controlbarBounds.width;

        const margin = 10;

        // These heights need to be non-zero for the below logic to work
        if (handleSpan === 0 || controlbarBoundsSpan === 0) {
            return;
        }

        let newCoord = viewportRelativeCoord;

        // Check if the coordinates are outside the control bar
        if (newCoord < controlbarBoundsStart + margin) {
            // Force coordinates to be below the start of the control bar
            newCoord = controlbarBoundsStart + margin;

        } else if (newCoord > controlbarBoundsStart +
                   controlbarBoundsSpan - handleSpan - margin) {
            // Force coordinates to be before the end of the control bar
            newCoord = controlbarBoundsStart +
                controlbarBoundsSpan - handleSpan - margin;
        }

        // Corner case: control bar too small for stable position
        if (controlbarBoundsSpan < (handleSpan + margin * 2)) {
            newCoord = controlbarBoundsStart +
                (controlbarBoundsSpan - handleSpan) / 2;
        }

        // The transform needs coordinates that are relative to the parent
        const parentRelativeCoord = newCoord - controlbarBoundsStart;
        if (isVertical) {
            handle.style.transform = "translateY(" + parentRelativeCoord + "px)";
        } else {
            handle.style.transform = "translateX(" + parentRelativeCoord + "px)";
        }
    },

    updateControlbarHandle() {
        // Since the control bar is fixed on the viewport and not the page,
        // the move function expects coordinates relative the the viewport.
        const handle = document.getElementById("webvnc_control_bar_handle");
        const handleBounds = handle.getBoundingClientRect();

        const controlBarPos = UI.getControlbarPos();
        const isVertical = controlBarPos === 'left' || controlBarPos === 'right';

        if (isVertical) {
            UI.moveControlbarHandle(handleBounds.top, true);
        } else {
            UI.moveControlbarHandle(handleBounds.left, false);
        }
    },

    controlbarHandleMouseUp(e) {
        if ((e.type == "mouseup") && (e.button != 0)) return;

        // mouseup and mousedown on the same place toggles the controlbar
        if (UI.controlbarGrabbed && !UI.controlbarDrag) {
            UI.toggleControlbar();
            e.preventDefault();
            e.stopPropagation();
            UI.keepControlbar();
            UI.activateControlbar();
        }
        UI.controlbarGrabbed = false;
        UI.showControlbarHint(false);
    },

    controlbarHandleMouseDown(e) {
        if ((e.type == "mousedown") && (e.button != 0)) return;

        const ptr = getPointerEvent(e);

        const handle = document.getElementById("webvnc_control_bar_handle");
        const bounds = handle.getBoundingClientRect();

        // Touch events have implicit capture
        if (e.type === "mousedown") {
            setCapture(handle);
        }

        UI.controlbarGrabbed = true;
        UI.controlbarDrag = false;

        UI.showControlbarHint(true);

        UI.controlbarMouseDownClientY = ptr.clientY;
        UI.controlbarMouseDownOffsetY = ptr.clientY - bounds.top;
        UI.controlbarMouseDownClientX = ptr.clientX;
        UI.controlbarMouseDownOffsetX = ptr.clientX - bounds.left;
        e.preventDefault();
        e.stopPropagation();
        UI.keepControlbar();
        UI.activateControlbar();
    },

    toggleExpander(e) {
        if (this.classList.contains("webvnc_open")) {
            this.classList.remove("webvnc_open");
        } else {
            this.classList.add("webvnc_open");
        }
    },

/* ------^-------
 *    /VISUAL
 * ==============
 *    SETTINGS
 * ------v------*/

    // Initial page load read/initialization of settings
    initSetting(name, defVal) {
        // Has the user overridden the default value?
        if (name in UI.customSettings.defaults) {
            defVal = UI.customSettings.defaults[name];
        }
        // Check Query string followed by cookie
        let val = WebUtil.getConfigVar(name);
        if (val === null) {
            val = WebUtil.readSetting(name, defVal);
        }
        WebUtil.setSetting(name, val);
        UI.updateSetting(name);
        // Has the user forced a value?
        if (name in UI.customSettings.mandatory) {
            val = UI.customSettings.mandatory[name];
            UI.forceSetting(name, val);
        }
        return val;
    },

    // Set the new value, update and disable form control setting
    forceSetting(name, val) {
        WebUtil.setSetting(name, val);
        UI.updateSetting(name);
        UI.disableSetting(name);
    },

    // Update cookie and form control setting. If value is not set, then
    // updates from control to current cookie setting.
    updateSetting(name) {

        // Update the settings control
        let value = UI.getSetting(name);

        const ctrl = document.getElementById('webvnc_setting_' + name);
        if (ctrl === null) {
            return;
        }

        if (ctrl.type === 'checkbox') {
            ctrl.checked = value;
        } else if (typeof ctrl.options !== 'undefined') {
            for (let i = 0; i < ctrl.options.length; i += 1) {
                if (ctrl.options[i].value === value) {
                    ctrl.selectedIndex = i;
                    break;
                }
            }
        } else {
            ctrl.value = value;
        }
    },

    // Save control setting to cookie
    saveSetting(name) {
        const ctrl = document.getElementById('webvnc_setting_' + name);
        let val;
        if (ctrl.type === 'checkbox') {
            val = ctrl.checked;
        } else if (typeof ctrl.options !== 'undefined') {
            val = ctrl.options[ctrl.selectedIndex].value;
        } else {
            val = ctrl.value;
        }
        WebUtil.writeSetting(name, val);
        //Log.Debug("Setting saved '" + name + "=" + val + "'");
        return val;
    },

    // Read form control compatible setting from cookie
    getSetting(name) {
        const ctrl = document.getElementById('webvnc_setting_' + name);
        let val = WebUtil.readSetting(name);
        if (typeof val !== 'undefined' && val !== null &&
            ctrl !== null && ctrl.type === 'checkbox') {
            if (val.toString().toLowerCase() in {'0': 1, 'no': 1, 'false': 1}) {
                val = false;
            } else {
                val = true;
            }
        }
        return val;
    },

    // These helpers compensate for the lack of parent-selectors and
    // previous-sibling-selectors in CSS which are needed when we want to
    // disable the labels that belong to disabled input elements.
    disableSetting(name) {
        const ctrl = document.getElementById('webvnc_setting_' + name);
        if (ctrl !== null) {
            ctrl.disabled = true;
            if (ctrl.label !== undefined) {
                ctrl.label.classList.add('webvnc_disabled');
            }
        }
    },

    enableSetting(name) {
        const ctrl = document.getElementById('webvnc_setting_' + name);
        if (ctrl !== null) {
            ctrl.disabled = false;
            if (ctrl.label !== undefined) {
                ctrl.label.classList.remove('webvnc_disabled');
            }
        }
    },

/* ------^-------
 *   /SETTINGS
 * ==============
 *    PANELS
 * ------v------*/

    closeAllPanels() {
        UI.closeSettingsPanel();
        UI.closePowerPanel();
        UI.closeClipboardPanel();
        UI.closeExtraKeys();
    },

/* ------^-------
 *   /PANELS
 * ==============
 * SETTINGS (panel)
 * ------v------*/

    openSettingsPanel() {
        UI.closeAllPanels();
        UI.openControlbar();

        // Refresh UI elements from saved cookies
        UI.updateSetting('encrypt');
        UI.updateSetting('view_clip');
        UI.updateSetting('resize');
        UI.updateSetting('quality');
        UI.updateSetting('compression');
        UI.updateSetting('shared');
        UI.updateSetting('view_only');
        UI.updateSetting('path');
        UI.updateSetting('repeaterID');
        UI.updateSetting('logging');
        UI.updateSetting('reconnect');
        UI.updateSetting('reconnect_delay');

        document.getElementById('webvnc_settings')
            .classList.add("webvnc_open");
        document.getElementById('webvnc_settings_button')
            .classList.add("webvnc_selected");
    },

    closeSettingsPanel() {
        document.getElementById('webvnc_settings')
            .classList.remove("webvnc_open");
        document.getElementById('webvnc_settings_button')
            .classList.remove("webvnc_selected");
    },

    toggleSettingsPanel() {
        if (document.getElementById('webvnc_settings')
            .classList.contains("webvnc_open")) {
            UI.closeSettingsPanel();
        } else {
            UI.openSettingsPanel();
        }
    },

/* ------^-------
 *   /SETTINGS
 * ==============
 *     POWER
 * ------v------*/

    openPowerPanel() {
        UI.closeAllPanels();
        UI.openControlbar();

        document.getElementById('webvnc_power')
            .classList.add("webvnc_open");
        document.getElementById('webvnc_power_button')
            .classList.add("webvnc_selected");
    },

    closePowerPanel() {
        document.getElementById('webvnc_power')
            .classList.remove("webvnc_open");
        document.getElementById('webvnc_power_button')
            .classList.remove("webvnc_selected");
    },

    togglePowerPanel() {
        if (document.getElementById('webvnc_power')
            .classList.contains("webvnc_open")) {
            UI.closePowerPanel();
        } else {
            UI.openPowerPanel();
        }
    },

    // Disable/enable power button
    updatePowerButton() {
        if (UI.connected &&
            UI.rfb.capabilities.power &&
            !UI.rfb.viewOnly) {
            document.getElementById('webvnc_power_button')
                .classList.remove("webvnc_hidden");
        } else {
            document.getElementById('webvnc_power_button')
                .classList.add("webvnc_hidden");
            // Close power panel if open
            UI.closePowerPanel();
        }
    },

/* ------^-------
 *    /POWER
 * ==============
 *   CLIPBOARD
 * ------v------*/

    openClipboardPanel() {
        UI.closeAllPanels();
        UI.openControlbar();

        document.getElementById('webvnc_clipboard')
            .classList.add("webvnc_open");
        document.getElementById('webvnc_clipboard_button')
            .classList.add("webvnc_selected");
    },

    closeClipboardPanel() {
        document.getElementById('webvnc_clipboard')
            .classList.remove("webvnc_open");
        document.getElementById('webvnc_clipboard_button')
            .classList.remove("webvnc_selected");
    },

    toggleClipboardPanel() {
        if (document.getElementById('webvnc_clipboard')
            .classList.contains("webvnc_open")) {
            UI.closeClipboardPanel();
        } else {
            UI.openClipboardPanel();
        }
    },

    clipboardReceive(e) {
        Log.Debug(">> UI.clipboardReceive: " + e.detail.text.substr(0, 40) + "...");
        document.getElementById('webvnc_clipboard_text').value = e.detail.text;
        Log.Debug("<< UI.clipboardReceive");
    },

    clipboardSend() {
        const text = document.getElementById('webvnc_clipboard_text').value;
        Log.Debug(">> UI.clipboardSend: " + text.substr(0, 40) + "...");
        UI.rfb.clipboardPasteFrom(text);
        Log.Debug("<< UI.clipboardSend");
    },

/* ------^-------
 *  /CLIPBOARD
 * ==============
 *  CONNECTION
 * ------v------*/

    connect(event, password) {

        // Ignore when rfb already exists
        if (typeof UI.rfb !== 'undefined') {
            return;
        }

        if (typeof password === 'undefined') {
            password = UI.getSetting('password');
            UI.reconnectPassword = password;
        }

        if (password === null) {
            password = undefined;
        }

        UI.hideStatus();

        UI.updateVisualState('connecting');

        if (UI.getSetting('keep_device_awake')) {
            UI.wakeLockManager.acquire();
        }

        // 使用当前 origin 的 /websockify，避免旧设置把连接发往别处，
        // 并附加登录会话令牌与角色供服务端鉴权。
        const url = new URL("/websockify", window.location.origin);
        url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        if (window.location.port) url.port = window.location.port;
        const auth = window.__WEBVNC_AUTH;
        if (auth && auth.getToken()) {
            url.searchParams.set("auth", auth.getToken());
        }
        // 角色始终随连接传递：none 模式下观察者即使无令牌也能保持只读
        if (auth && auth.getRole()) {
            url.searchParams.set("role", auth.getRole());
        }

        try {
            UI.rfb = new RFB(document.getElementById('webvnc_container'),
                             url.href,
                             { shared: UI.getSetting('shared'),
                               repeaterID: UI.getSetting('repeaterID'),
                               credentials: { password: password } });
        } catch (exc) {
            Log.Error("Failed to connect to server: " + exc);
            UI.updateVisualState('disconnected');
            UI.showStatus(_("Failed to connect to server: ") + exc, 'error');
            return;
        }
        UI.rfb.viewOnly = !!(auth && auth.getRole() === "observer");

        UI.rfb.addEventListener("connect", UI.connectFinished);
        UI.rfb.addEventListener("disconnect", UI.disconnectFinished);
        UI.rfb.addEventListener("serververification", UI.serverVerify);
        UI.rfb.addEventListener("credentialsrequired", UI.credentials);
        UI.rfb.addEventListener("securityfailure", UI.securityFailed);
        UI.rfb.addEventListener("clippingviewport", UI.updateViewDrag);
        UI.rfb.addEventListener("capabilities", UI.updatePowerButton);
        UI.rfb.addEventListener("clipboard", UI.clipboardReceive);
        UI.rfb.addEventListener("bell", UI.bell);
        UI.rfb.addEventListener("desktopname", UI.updateDesktopName);
        UI.rfb.clipViewport = UI.getSetting('view_clip');
        UI.rfb.scaleViewport = UI.getSetting('resize') === 'scale';
        UI.rfb.resizeSession = UI.getSetting('resize') === 'remote';
        UI.rfb.qualityLevel = parseInt(UI.getSetting('quality'));
        UI.rfb.compressionLevel = parseInt(UI.getSetting('compression'));
        UI.rfb.showDotCursor = UI.getSetting('show_dot');

        UI.updateViewOnly(); // requires UI.rfb
        UI.updateClipboard();
    },

    disconnect() {
        UI.rfb.disconnect();

        UI.connected = false;

        // Disable automatic reconnecting
        UI.inhibitReconnect = true;

        UI.updateVisualState('disconnecting');

        // Don't display the connection settings until we're actually disconnected
    },

    reconnect() {
        UI.reconnectCallback = null;

        // if reconnect has been disabled in the meantime, do nothing.
        if (UI.inhibitReconnect) {
            return;
        }

        UI.connect(null, UI.reconnectPassword);
    },

    cancelReconnect() {
        if (UI.reconnectCallback !== null) {
            clearTimeout(UI.reconnectCallback);
            UI.reconnectCallback = null;
        }

        UI.updateVisualState('disconnected');

        UI.openControlbar();
    },

    connectFinished(e) {
        UI.connected = true;
        UI.inhibitReconnect = false;

        let msg;
        if (UI.getSetting('encrypt')) {
            msg = _("Connected (encrypted) to ") + UI.desktopName;
        } else {
            msg = _("Connected (unencrypted) to ") + UI.desktopName;
        }
        UI.showStatus(msg);
        UI.updateVisualState('connected');

        UI.updateBeforeUnload();

        // Do this last because it can only be used on rendered elements
        UI.rfb.focus();
    },

    disconnectFinished(e) {
        const wasConnected = UI.connected;

        // This variable is ideally set when disconnection starts, but
        // when the disconnection isn't clean or if it is initiated by
        // the server, we need to do it here as well since
        // UI.disconnect() won't be used in those cases.
        UI.connected = false;

        UI.rfb = undefined;
        UI.wakeLockManager.release();

        if (!e.detail.clean) {
            UI.updateVisualState('disconnected');
            if (wasConnected) {
                UI.showStatus(_("Something went wrong, connection is closed"),
                              'error');
            } else {
                UI.showStatus(_("Failed to connect to server"), 'error');
            }
        }
        // If reconnecting is allowed process it now
        if (UI.getSetting('reconnect', false) === true && !UI.inhibitReconnect) {
            UI.updateVisualState('reconnecting');

            const delay = parseInt(UI.getSetting('reconnect_delay'));
            UI.reconnectCallback = setTimeout(UI.reconnect, delay);
            return;
        } else {
            UI.updateVisualState('disconnected');
            UI.showStatus(_("Disconnected"), 'normal');
        }

        UI.updateBeforeUnload();

        document.title = PAGE_TITLE;

        UI.openControlbar();
    },

    securityFailed(e) {
        let msg;
        // On security failures we might get a string with a reason
        // directly from the server. Note that we can't control if
        // this string is translated or not.
        if ('reason' in e.detail) {
            msg = _("New connection has been rejected with reason: ") +
                e.detail.reason;
        } else {
            msg = _("New connection has been rejected");
        }
        UI.showStatus(msg, 'error');
    },

    handleBeforeUnload(e) {
        // Trigger a "Leave site?" warning prompt before closing the
        // page. Modern browsers (Oct 2025) accept either (or both)
        // preventDefault() or a nonempty returnValue, though the latter is
        // considered legacy. The custom string is ignored by modern browsers,
        // which display a native message, but older browsers will show it.
        e.preventDefault();
        e.returnValue = _("Are you sure you want to disconnect the session?");
    },

    updateBeforeUnload() {
        // Remove first to avoid adding duplicates
        window.removeEventListener("beforeunload", UI.handleBeforeUnload);
        if (!UI.rfb?.viewOnly && UI.connected) {
            window.addEventListener("beforeunload", UI.handleBeforeUnload);
        }
    },

/* ------^-------
 *  /CONNECTION
 * ==============
 * SERVER VERIFY
 * ------v------*/

    async serverVerify(e) {
        const type = e.detail.type;
        if (type === 'RSA') {
            const publickey = e.detail.publickey;
            let fingerprint = await window.crypto.subtle.digest("SHA-1", publickey);
            // The same fingerprint format as RealVNC
            fingerprint = Array.from(new Uint8Array(fingerprint).slice(0, 8)).map(
                x => x.toString(16).padStart(2, '0')).join('-');
            document.getElementById('webvnc_verify_server_dlg').classList.add('webvnc_open');
            document.getElementById('webvnc_fingerprint').innerHTML = fingerprint;
        }
    },

    approveServer(e) {
        e.preventDefault();
        document.getElementById('webvnc_verify_server_dlg').classList.remove('webvnc_open');
        UI.rfb.approveServer();
    },

    rejectServer(e) {
        e.preventDefault();
        document.getElementById('webvnc_verify_server_dlg').classList.remove('webvnc_open');
        UI.disconnect();
    },

/* ------^-------
 * /SERVER VERIFY
 * ==============
 *   PASSWORD
 * ------v------*/

    credentials(e) {
        // FIXME: handle more types

        document.getElementById("webvnc_username_block").classList.remove("webvnc_hidden");
        document.getElementById("webvnc_password_block").classList.remove("webvnc_hidden");

        let inputFocus = "none";
        if (e.detail.types.indexOf("username") === -1) {
            document.getElementById("webvnc_username_block").classList.add("webvnc_hidden");
        } else if (document.getElementById("webvnc_username_input").value === "") {
            inputFocus = "webvnc_username_input";
        }
        if (e.detail.types.indexOf("password") === -1) {
            document.getElementById("webvnc_password_block").classList.add("webvnc_hidden");
        } else if (inputFocus === "none") {
            inputFocus = "webvnc_password_input";
        }
        document.getElementById('webvnc_credentials_dlg')
            .classList.add('webvnc_open');

        setTimeout(() => document
            .getElementById(inputFocus).focus(), 100);

        Log.Warn("Server asked for credentials");
        UI.showStatus(_("Credentials are required"), "warning");
    },

    setCredentials(e) {
        // Prevent actually submitting the form
        e.preventDefault();

        let inputElemUsername = document.getElementById('webvnc_username_input');
        const username = inputElemUsername.value;

        let inputElemPassword = document.getElementById('webvnc_password_input');
        const password = inputElemPassword.value;
        // Clear the input after reading the password
        inputElemPassword.value = "";

        UI.rfb.sendCredentials({ username: username, password: password });
        UI.reconnectPassword = password;
        document.getElementById('webvnc_credentials_dlg')
            .classList.remove('webvnc_open');
    },

/* ------^-------
 *  /PASSWORD
 * ==============
 *   FULLSCREEN
 * ------v------*/

    toggleFullscreen() {
        if (document.fullscreenElement || // alternative standard method
            document.mozFullScreenElement || // currently working methods
            document.webkitFullscreenElement ||
            document.msFullscreenElement) {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.mozCancelFullScreen) {
                document.mozCancelFullScreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            }
        } else {
            if (document.documentElement.requestFullscreen) {
                document.documentElement.requestFullscreen();
            } else if (document.documentElement.mozRequestFullScreen) {
                document.documentElement.mozRequestFullScreen();
            } else if (document.documentElement.webkitRequestFullscreen) {
                document.documentElement.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
            } else if (document.body.msRequestFullscreen) {
                document.body.msRequestFullscreen();
            }
        }
        UI.updateFullscreenButton();
    },

    updateFullscreenButton() {
        if (document.fullscreenElement || // alternative standard method
            document.mozFullScreenElement || // currently working methods
            document.webkitFullscreenElement ||
            document.msFullscreenElement ) {
            document.getElementById('webvnc_fullscreen_button')
                .classList.add("webvnc_selected");
        } else {
            document.getElementById('webvnc_fullscreen_button')
                .classList.remove("webvnc_selected");
        }
    },

/* ------^-------
 *  /FULLSCREEN
 * ==============
 *     RESIZE
 * ------v------*/

    // Apply remote resizing or local scaling
    applyResizeMode() {
        if (!UI.rfb) return;

        UI.rfb.scaleViewport = UI.getSetting('resize') === 'scale';
        UI.rfb.resizeSession = UI.getSetting('resize') === 'remote';
    },

/* ------^-------
 *    /RESIZE
 * ==============
 * VIEW CLIPPING
 * ------v------*/

    // Update viewport clipping property for the connection. The normal
    // case is to get the value from the setting. There are special cases
    // for when the viewport is scaled or when a touch device is used.
    updateViewClip() {
        if (!UI.rfb) return;

        const scaling = UI.getSetting('resize') === 'scale';

        // Some platforms have overlay scrollbars that are difficult
        // to use in our case, which means we have to force panning
        // FIXME: Working scrollbars can still be annoying to use with
        //        touch, so we should ideally be able to have both
        //        panning and scrollbars at the same time

        let brokenScrollbars = false;

        if (!hasScrollbarGutter) {
            if (isIOS() || isAndroid() || isMac() || isChromeOS()) {
                brokenScrollbars = true;
            }
        }

        if (scaling) {
            // Can't be clipping if viewport is scaled to fit
            UI.forceSetting('view_clip', false);
            UI.rfb.clipViewport  = false;
        } else if (brokenScrollbars) {
            UI.forceSetting('view_clip', true);
            UI.rfb.clipViewport = true;
        } else {
            UI.enableSetting('view_clip');
            UI.rfb.clipViewport = UI.getSetting('view_clip');
        }

        // Changing the viewport may change the state of
        // the dragging button
        UI.updateViewDrag();
    },

/* ------^-------
 * /VIEW CLIPPING
 * ==============
 *    VIEWDRAG
 * ------v------*/

    toggleViewDrag() {
        if (!UI.rfb) return;

        UI.rfb.dragViewport = !UI.rfb.dragViewport;
        UI.updateViewDrag();
    },

    updateViewDrag() {
        if (!UI.connected) return;

        const viewDragButton = document.getElementById('webvnc_view_drag_button');

        if ((!UI.rfb.clipViewport || !UI.rfb.clippingViewport) &&
            UI.rfb.dragViewport) {
            // We are no longer clipping the viewport. Make sure
            // viewport drag isn't active when it can't be used.
            UI.rfb.dragViewport = false;
        }

        if (UI.rfb.dragViewport) {
            viewDragButton.classList.add("webvnc_selected");
        } else {
            viewDragButton.classList.remove("webvnc_selected");
        }

        if (UI.rfb.clipViewport) {
            viewDragButton.classList.remove("webvnc_hidden");
        } else {
            viewDragButton.classList.add("webvnc_hidden");
        }

        viewDragButton.disabled = !UI.rfb.clippingViewport;
    },

/* ------^-------
 *   /VIEWDRAG
 * ==============
 *    QUALITY
 * ------v------*/

    updateQuality() {
        if (!UI.rfb) return;

        UI.rfb.qualityLevel = parseInt(UI.getSetting('quality'));
    },

/* ------^-------
 *   /QUALITY
 * ==============
 *  COMPRESSION
 * ------v------*/

    updateCompression() {
        if (!UI.rfb) return;

        UI.rfb.compressionLevel = parseInt(UI.getSetting('compression'));
    },

/* ------^-------
 *  /COMPRESSION
 * ==============
 *    KEYBOARD
 * ------v------*/

    showVirtualKeyboard() {
        if (!isTouchDevice) return;

        const input = document.getElementById('webvnc_keyboardinput');

        if (document.activeElement == input) return;

        input.focus();

        try {
            const l = input.value.length;
            // Move the caret to the end
            input.setSelectionRange(l, l);
        } catch (err) {
            // setSelectionRange is undefined in Google Chrome
        }
    },

    hideVirtualKeyboard() {
        if (!isTouchDevice) return;

        const input = document.getElementById('webvnc_keyboardinput');

        if (document.activeElement != input) return;

        input.blur();
    },

    toggleVirtualKeyboard() {
        if (document.getElementById('webvnc_keyboard_button')
            .classList.contains("webvnc_selected")) {
            UI.hideVirtualKeyboard();
        } else {
            UI.showVirtualKeyboard();
        }
    },

    onfocusVirtualKeyboard(event) {
        document.getElementById('webvnc_keyboard_button')
            .classList.add("webvnc_selected");
        if (UI.rfb) {
            UI.rfb.focusOnClick = false;
        }
    },

    onblurVirtualKeyboard(event) {
        document.getElementById('webvnc_keyboard_button')
            .classList.remove("webvnc_selected");
        if (UI.rfb) {
            UI.rfb.focusOnClick = true;
        }
    },

    keepVirtualKeyboard(event) {
        const input = document.getElementById('webvnc_keyboardinput');

        // Only prevent focus change if the virtual keyboard is active
        if (document.activeElement != input) {
            return;
        }

        // Only allow focus to move to other elements that need
        // focus to function properly
        if (event.target.form !== undefined) {
            switch (event.target.type) {
                case 'text':
                case 'email':
                case 'search':
                case 'password':
                case 'tel':
                case 'url':
                case 'textarea':
                case 'select-one':
                case 'select-multiple':
                    return;
            }
        }

        event.preventDefault();
    },

    keyboardinputReset() {
        const kbi = document.getElementById('webvnc_keyboardinput');
        kbi.value = new Array(UI.defaultKeyboardinputLen).join("_");
        UI.lastKeyboardinput = kbi.value;
    },

    keyEvent(keysym, code, down) {
        if (!UI.rfb) return;

        UI.rfb.sendKey(keysym, code, down);
    },

    // When normal keyboard events are left uncought, use the input events from
    // the keyboardinput element instead and generate the corresponding key events.
    // This code is required since some browsers on Android are inconsistent in
    // sending keyCodes in the normal keyboard events when using on screen keyboards.
    keyInput(event) {

        if (!UI.rfb) return;

        const newValue = event.target.value;

        if (!UI.lastKeyboardinput) {
            UI.keyboardinputReset();
        }
        const oldValue = UI.lastKeyboardinput;

        let newLen;
        try {
            // Try to check caret position since whitespace at the end
            // will not be considered by value.length in some browsers
            newLen = Math.max(event.target.selectionStart, newValue.length);
        } catch (err) {
            // selectionStart is undefined in Google Chrome
            newLen = newValue.length;
        }
        const oldLen = oldValue.length;

        let inputs = newLen - oldLen;
        let backspaces = inputs < 0 ? -inputs : 0;

        // Compare the old string with the new to account for
        // text-corrections or other input that modify existing text
        for (let i = 0; i < Math.min(oldLen, newLen); i++) {
            if (newValue.charAt(i) != oldValue.charAt(i)) {
                inputs = newLen - i;
                backspaces = oldLen - i;
                break;
            }
        }

        // Send the key events
        for (let i = 0; i < backspaces; i++) {
            UI.rfb.sendKey(KeyTable.XK_BackSpace, "Backspace");
        }
        for (let i = newLen - inputs; i < newLen; i++) {
            UI.rfb.sendKey(keysyms.lookup(newValue.charCodeAt(i)));
        }

        // Control the text content length in the keyboardinput element
        if (newLen > 2 * UI.defaultKeyboardinputLen) {
            UI.keyboardinputReset();
        } else if (newLen < 1) {
            // There always have to be some text in the keyboardinput
            // element with which backspace can interact.
            UI.keyboardinputReset();
            // This sometimes causes the keyboard to disappear for a second
            // but it is required for the android keyboard to recognize that
            // text has been added to the field
            event.target.blur();
            // This has to be ran outside of the input handler in order to work
            setTimeout(event.target.focus.bind(event.target), 0);
        } else {
            UI.lastKeyboardinput = newValue;
        }
    },

/* ------^-------
 *   /KEYBOARD
 * ==============
 *   EXTRA KEYS
 * ------v------*/

    openExtraKeys() {
        UI.closeAllPanels();
        UI.openControlbar();

        document.getElementById('webvnc_modifiers')
            .classList.add("webvnc_open");
        document.getElementById('webvnc_toggle_extra_keys_button')
            .classList.add("webvnc_selected");
    },

    closeExtraKeys() {
        document.getElementById('webvnc_modifiers')
            .classList.remove("webvnc_open");
        document.getElementById('webvnc_toggle_extra_keys_button')
            .classList.remove("webvnc_selected");
    },

    toggleExtraKeys() {
        if (document.getElementById('webvnc_modifiers')
            .classList.contains("webvnc_open")) {
            UI.closeExtraKeys();
        } else  {
            UI.openExtraKeys();
        }
    },

    sendEsc() {
        UI.sendKey(KeyTable.XK_Escape, "Escape");
    },

    sendTab() {
        UI.sendKey(KeyTable.XK_Tab, "Tab");
    },

    toggleCtrl() {
        const btn = document.getElementById('webvnc_toggle_ctrl_button');
        if (btn.classList.contains("webvnc_selected")) {
            UI.sendKey(KeyTable.XK_Control_L, "ControlLeft", false);
            btn.classList.remove("webvnc_selected");
        } else {
            UI.sendKey(KeyTable.XK_Control_L, "ControlLeft", true);
            btn.classList.add("webvnc_selected");
        }
    },

    toggleWindows() {
        const btn = document.getElementById('webvnc_toggle_windows_button');
        if (btn.classList.contains("webvnc_selected")) {
            UI.sendKey(KeyTable.XK_Super_L, "MetaLeft", false);
            btn.classList.remove("webvnc_selected");
        } else {
            UI.sendKey(KeyTable.XK_Super_L, "MetaLeft", true);
            btn.classList.add("webvnc_selected");
        }
    },

    toggleAlt() {
        const btn = document.getElementById('webvnc_toggle_alt_button');
        if (btn.classList.contains("webvnc_selected")) {
            UI.sendKey(KeyTable.XK_Alt_L, "AltLeft", false);
            btn.classList.remove("webvnc_selected");
        } else {
            UI.sendKey(KeyTable.XK_Alt_L, "AltLeft", true);
            btn.classList.add("webvnc_selected");
        }
    },

    sendCtrlAltDel() {
        UI.rfb.sendCtrlAltDel();
        // See below
        UI.rfb.focus();
        UI.idleControlbar();
    },

    sendKey(keysym, code, down) {
        UI.rfb.sendKey(keysym, code, down);

        // Move focus to the screen in order to be able to use the
        // keyboard right after these extra keys.
        // The exception is when a virtual keyboard is used, because
        // if we focus the screen the virtual keyboard would be closed.
        // In this case we focus our special virtual keyboard input
        // element instead.
        if (document.getElementById('webvnc_keyboard_button')
            .classList.contains("webvnc_selected")) {
            document.getElementById('webvnc_keyboardinput').focus();
        } else {
            UI.rfb.focus();
        }
        // fade out the controlbar to highlight that
        // the focus has been moved to the screen
        UI.idleControlbar();
    },

/* ------^-------
 *   /EXTRA KEYS
 * ==============
 *     MISC
 * ------v------*/

    updateViewOnly() {
        if (!UI.rfb) return;
        UI.rfb.viewOnly = UI.getSetting('view_only');

        UI.updateBeforeUnload();

        // Hide input related buttons in view only mode
        if (UI.rfb.viewOnly) {
            document.getElementById('webvnc_keyboard_button')
                .classList.add('webvnc_hidden');
            document.getElementById('webvnc_toggle_extra_keys_button')
                .classList.add('webvnc_hidden');
            document.getElementById('webvnc_clipboard_button')
                .classList.add('webvnc_hidden');
        } else {
            document.getElementById('webvnc_keyboard_button')
                .classList.remove('webvnc_hidden');
            document.getElementById('webvnc_toggle_extra_keys_button')
                .classList.remove('webvnc_hidden');
            document.getElementById('webvnc_clipboard_button')
                .classList.remove('webvnc_hidden');
        }
    },

    updateClipboard() {
        browserAsyncClipboardSupport()
            .then((support) => {
                if (support === 'unsupported') {
                    // Use fallback clipboard panel
                    return;
                }
                if (support === 'denied' || support === 'available') {
                    UI.closeClipboardPanel();
                    document.getElementById('webvnc_clipboard_button')
                        .classList.add('webvnc_hidden');
                    document.getElementById('webvnc_clipboard_button')
                        .removeEventListener('click', UI.toggleClipboardPanel);
                    document.getElementById('webvnc_clipboard_text')
                        .removeEventListener('change', UI.clipboardSend);
                    if (UI.rfb) {
                        UI.rfb.removeEventListener('clipboard', UI.clipboardReceive);
                    }
                }
            })
            .catch(() => {
                // Treat as unsupported
            });
    },

    updateShowDotCursor() {
        if (!UI.rfb) return;
        UI.rfb.showDotCursor = UI.getSetting('show_dot');
    },

    updateLogging() {
        WebUtil.initLogging(UI.getSetting('logging'));
    },

    updateDesktopName(e) {
        UI.desktopName = e.detail.name;
        // Display the desktop name in the document title
        if (e.detail.name && e.detail.name !== PAGE_TITLE) {
            document.title = e.detail.name + " - " + PAGE_TITLE;
        } else {
            document.title = PAGE_TITLE;
        }
    },

    updateRequestWakelock() {
        if (!UI.rfb) return;
        if (UI.getSetting('keep_device_awake')) {
            UI.wakeLockManager.acquire();
        } else {
            UI.wakeLockManager.release();
        }
    },


    bell(e) {
        if (UI.getSetting('bell') === 'on') {
            const promise = document.getElementById('webvnc_bell').play();
            // The standards disagree on the return value here
            if (promise) {
                promise.catch((e) => {
                    if (e.name === "NotAllowedError") {
                        // Ignore when the browser doesn't let us play audio.
                        // It is common that the browsers require audio to be
                        // initiated from a user action.
                    } else {
                        Log.Error("Unable to play bell: " + e);
                    }
                });
            }
        }
    },

    //Helper to add options to dropdown.
    addOption(selectbox, text, value) {
        const optn = document.createElement("OPTION");
        optn.text = text;
        optn.value = value;
        selectbox.options.add(optn);
    },

/* ------^-------
 *    /MISC
 * ==============
 */
};

export default UI;
