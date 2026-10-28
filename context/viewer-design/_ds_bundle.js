/* @ds-bundle: {"format":4,"namespace":"MyDefaultDesignSystem_f28e8c","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"SectionHeader","sourcePath":"components/core/SectionHeader.jsx"},{"name":"Chart","sourcePath":"components/data/Chart.jsx"},{"name":"ListRow","sourcePath":"components/data/ListRow.jsx"},{"name":"Progress","sourcePath":"components/data/Progress.jsx"},{"name":"Readout","sourcePath":"components/data/Readout.jsx"},{"name":"Swatch","sourcePath":"components/data/Swatch.jsx"},{"name":"Dialog","sourcePath":"components/feedback/Dialog.jsx"},{"name":"Notice","sourcePath":"components/feedback/Notice.jsx"},{"name":"Snackbar","sourcePath":"components/feedback/Snackbar.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Chip","sourcePath":"components/forms/Chip.jsx"},{"name":"SegmentedControl","sourcePath":"components/forms/SegmentedControl.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"},{"name":"TextField","sourcePath":"components/forms/TextField.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"4ed8c2511eaa","components/core/Button.jsx":"1db0ad7b77f6","components/core/Card.jsx":"342233d73ea7","components/core/Icon.jsx":"71f490e781aa","components/core/SectionHeader.jsx":"24d9afd6db0b","components/data/Chart.jsx":"d906b76d78af","components/data/ListRow.jsx":"ba8bbd2ddcdc","components/data/Progress.jsx":"b5de19ad6ced","components/data/Readout.jsx":"9de26753e0eb","components/data/Swatch.jsx":"3a369aced021","components/feedback/Dialog.jsx":"6e34da5e5af3","components/feedback/Notice.jsx":"12329f0b9cd1","components/feedback/Snackbar.jsx":"740b9d483584","components/forms/Checkbox.jsx":"fd01ddac85b0","components/forms/Chip.jsx":"74c64f513858","components/forms/SegmentedControl.jsx":"b8f574380e28","components/forms/Switch.jsx":"af8ebef94829","components/forms/TextField.jsx":"db066c4fca41","components/navigation/Tabs.jsx":"9b819a37911c","ui_kits/style-guide/ComponentGallery.jsx":"719197673443","ui_kits/style-guide/StyleGuide.jsx":"7c93b2ee51ff"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.MyDefaultDesignSystem_f28e8c = window.MyDefaultDesignSystem_f28e8c || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const cx = (...a) => a.filter(Boolean).join(' ');
function Card({
  title,
  action,
  elevation = 'flat',
  padding = 'default',
  className,
  children,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("section", _extends({}, rest, {
    className: cx('md-card', elevation === 'raised' && 'md-card-raised', padding === 'none' && 'md-card-flush', className)
  }), title || action ? /*#__PURE__*/React.createElement("header", {
    className: "md-card-head"
  }, title ? /*#__PURE__*/React.createElement("h3", {
    className: "md-card-title"
  }, title) : null, action || null) : null, children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Icon.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
const ICONS = {
  file: ['M6 3.5 L14 3.5 L18.5 8 L18.5 20.5 L6 20.5 Z', 'M13.5 3.5 L13.5 8.5 L18.5 8.5'],
  folder: ['M4 7 L4 18.5 L20 18.5 L20 9 L11.5 9 L9.5 6 L4 6 Z'],
  chart: ['M4 4 L4 20 L20 20', 'M7.5 15 L11 11 L14 13.5 L19 7.5'],
  plus: ['M12 5 L12 19', 'M5 12 L19 12'],
  check: ['M5 12.5 L10 17.5 L19 7'],
  search: ['M10.5 4.5 A6 6 0 1 1 10.49 4.5 Z', 'M15 15 L20 20'],
  download: ['M12 4 L12 15', 'M7.5 10.5 L12 15 L16.5 10.5', 'M5 19.5 L19 19.5'],
  flag: ['M6 20.5 L6 4', 'M6 4.5 L17 4.5 L14.5 8.5 L17 12.5 L6 12.5'],
  play: ['M8 5.5 L18 12 L8 18.5 Z'],
  pause: ['M8.5 5.5 L8.5 18.5', 'M15.5 5.5 L15.5 18.5'],
  chevron: ['M6 9 L12 15 L18 9'],
  close: ['M6 6 L18 18', 'M18 6 L6 18'],
  live: ['M12 10.5 A1.5 1.5 0 1 1 11.99 10.5 Z', 'M8.5 8.5 A5 5 0 0 0 8.5 15.5', 'M15.5 8.5 A5 5 0 0 1 15.5 15.5', 'M5.5 5.5 A9 9 0 0 0 5.5 18.5', 'M18.5 5.5 A9 9 0 0 1 18.5 18.5'],
  loader: ['M12 4 A8 8 0 1 1 4 12'],
  refresh: ['M18.5 9.5 A7 7 0 0 0 5.2 10.5', 'M5.5 14.5 A7 7 0 0 0 18.8 13.5', 'M18.5 5 L18.5 9.5 L14 9.5', 'M5.5 19 L5.5 14.5 L10 14.5'],
  clock: ['M12 4 A8 8 0 1 1 11.99 4 Z', 'M12 8 L12 12 L15 14'],
  alert: ['M12 4.5 L20.5 19 L3.5 19 Z', 'M12 10 L12 13.5', 'M12 16.25 L12 16.35'],
  error: ['M12 4 A8 8 0 1 1 11.99 4 Z', 'M9.5 9.5 L14.5 14.5', 'M14.5 9.5 L9.5 14.5']
};
const ICON_NAMES = Object.keys(ICONS);
/** Outline icon on the 24 grid with a 1.5 round stroke. Inherits currentColor. */
function Icon({
  name,
  size = 16,
  className
}) {
  const paths = ICONS[name] || ICONS.file;
  return /*#__PURE__*/React.createElement("svg", {
    className: cx('md-icon', className),
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    "aria-hidden": "true"
  }, paths.map((d, i) => /*#__PURE__*/React.createElement("path", {
    key: i,
    d: d,
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round",
    strokeLinejoin: "round"
  })));
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
const TONE_ICON = {
  success: 'check',
  info: 'clock',
  warning: 'alert',
  danger: 'error'
};
function Badge({
  tone: toneIn = 'neutral',
  icon,
  children,
  className
}) {
  const tone = toneIn === 'subtle' ? 'neutral' : toneIn;
  const name = icon === false ? null : icon || TONE_ICON[tone];
  return /*#__PURE__*/React.createElement("span", {
    className: cx('md-badge', 'md-badge-' + tone, className)
  }, name ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: name,
    size: 14
  }) : null, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const cx = (...a) => a.filter(Boolean).join(' ');
function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  iconOnly,
  className,
  children,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button"
  }, rest, {
    className: cx('md-btn', 'md-btn-' + variant, 'md-btn-' + size, iconOnly && 'md-btn-icononly', className)
  }), icon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: size === 'sm' ? 14 : 16
  }) : null, iconOnly ? null : children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/SectionHeader.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
function SectionHeader({
  title,
  children,
  className
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: cx('md-section', className)
  }, /*#__PURE__*/React.createElement("h2", {
    className: "md-section-title"
  }, title), children ? /*#__PURE__*/React.createElement("p", {
    className: "md-section-intro"
  }, children) : null);
}
Object.assign(__ds_scope, { SectionHeader });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/SectionHeader.jsx", error: String((e && e.message) || e) }); }

// components/data/Chart.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
function Chart({
  data = [],
  title,
  value,
  label,
  xLabels,
  width = 640,
  height = 160,
  area = false,
  className
}) {
  const pad = 8;
  let min = Math.min(...data),
    max = Math.max(...data);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const pts = data.map((y, i) => [data.length > 1 ? i / (data.length - 1) * width : 0, pad + (1 - (y - min) / (max - min)) * (height - pad * 2)]);
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  const areaD = pts.length ? line + ' L' + width + ' ' + height + ' L0 ' + height + ' Z' : '';
  return /*#__PURE__*/React.createElement("figure", {
    className: cx('md-chart', className)
  }, title || value ? /*#__PURE__*/React.createElement("figcaption", {
    className: "md-chart-head"
  }, title ? /*#__PURE__*/React.createElement("span", {
    className: "md-chart-title"
  }, title) : null, value ? /*#__PURE__*/React.createElement("span", {
    className: "md-chart-value"
  }, value) : null) : null, /*#__PURE__*/React.createElement("svg", {
    className: "md-chart-plot",
    viewBox: '0 0 ' + width + ' ' + height,
    preserveAspectRatio: "none",
    style: {
      height
    },
    role: "img",
    "aria-label": label || title || 'Chart'
  }, /*#__PURE__*/React.createElement("line", {
    x1: 0,
    x2: width,
    y1: 0.5,
    y2: 0.5,
    className: "md-chart-grid",
    vectorEffect: "non-scaling-stroke"
  }), /*#__PURE__*/React.createElement("line", {
    x1: 0,
    x2: width,
    y1: height / 2,
    y2: height / 2,
    className: "md-chart-grid",
    vectorEffect: "non-scaling-stroke"
  }), /*#__PURE__*/React.createElement("line", {
    x1: 0,
    x2: width,
    y1: height - 0.5,
    y2: height - 0.5,
    className: "md-chart-base",
    vectorEffect: "non-scaling-stroke"
  }), area === false ? null : /*#__PURE__*/React.createElement("path", {
    d: areaD,
    className: "md-chart-area"
  }), /*#__PURE__*/React.createElement("path", {
    d: line,
    className: "md-chart-line",
    vectorEffect: "non-scaling-stroke"
  })), xLabels ? /*#__PURE__*/React.createElement("div", {
    className: "md-chart-axis"
  }, xLabels.map((l, i) => /*#__PURE__*/React.createElement("span", {
    key: i
  }, l))) : null);
}
Object.assign(__ds_scope, { Chart });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Chart.jsx", error: String((e && e.message) || e) }); }

// components/data/ListRow.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const cx = (...a) => a.filter(Boolean).join(' ');
function ListRow({
  icon = 'file',
  title,
  meta,
  values = [],
  status,
  selected,
  mono,
  className,
  style,
  onClick,
  onKeyDown,
  ...rest
}) {
  const key = e => {
    if (onKeyDown) onKeyDown(e);
    if (!e.defaultPrevented && onClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick(e);
    }
  };
  const cols = '20px minmax(0, 1fr)' + values.map(() => ' 96px').join('') + ' 128px';
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "row",
    tabIndex: onClick ? 0 : undefined,
    "aria-selected": selected ? 'true' : 'false'
  }, rest, {
    onClick: onClick,
    onKeyDown: key,
    className: cx('md-row', selected && 'md-row-selected', className),
    style: {
      gridTemplateColumns: cols,
      ...(style || {})
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "md-row-icon",
    role: "cell"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 18
  })), /*#__PURE__*/React.createElement("span", {
    className: "md-row-main",
    role: "cell"
  }, /*#__PURE__*/React.createElement("span", {
    className: cx('md-row-title', mono && 'md-row-title-mono')
  }, title), meta ? /*#__PURE__*/React.createElement("span", {
    className: "md-row-meta"
  }, meta) : null), values.map((v, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    className: "md-row-num",
    role: "cell"
  }, v)), /*#__PURE__*/React.createElement("span", {
    className: "md-row-status",
    role: "cell"
  }, status ? /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: status.tone,
    icon: status.icon
  }, status.label) : null));
}
Object.assign(__ds_scope, { ListRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/ListRow.jsx", error: String((e && e.message) || e) }); }

// components/data/Progress.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
function Progress({
  value = 0,
  label,
  tone: toneIn = 'brand',
  showValue,
  className
}) {
  const tone = toneIn === 'info' ? 'brand' : toneIn;
  const v = Math.max(0, Math.min(1, value || 0));
  const pct = Math.round(v * 100);
  return /*#__PURE__*/React.createElement("div", {
    className: cx('md-progress', className)
  }, label || showValue ? /*#__PURE__*/React.createElement("div", {
    className: "md-progress-head"
  }, label ? /*#__PURE__*/React.createElement("span", {
    className: "md-progress-label"
  }, label) : /*#__PURE__*/React.createElement("span", null), showValue ? /*#__PURE__*/React.createElement("span", {
    className: "md-progress-value"
  }, pct + '%') : null) : null, /*#__PURE__*/React.createElement("div", {
    className: "md-progress-track",
    role: "progressbar",
    "aria-label": label,
    "aria-valuemin": 0,
    "aria-valuemax": 100,
    "aria-valuenow": pct
  }, /*#__PURE__*/React.createElement("div", {
    className: 'md-progress-fill md-progress-' + tone,
    style: {
      width: v * 100 + '%'
    }
  })));
}
Object.assign(__ds_scope, { Progress });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Progress.jsx", error: String((e && e.message) || e) }); }

// components/data/Readout.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
function Readout({
  label,
  value,
  unit,
  size = 'md',
  className
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: cx('md-readout', size === 'lg' && 'md-readout-lg', className)
  }, /*#__PURE__*/React.createElement("div", {
    className: "md-readout-value"
  }, value, unit ? /*#__PURE__*/React.createElement("span", {
    className: "md-readout-unit"
  }, ' ' + unit) : null), /*#__PURE__*/React.createElement("div", {
    className: "md-readout-label"
  }, label));
}
Object.assign(__ds_scope, { Readout });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Readout.jsx", error: String((e && e.message) || e) }); }

// components/data/Swatch.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
function Swatch({
  name,
  value,
  color,
  className
}) {
  return /*#__PURE__*/React.createElement("figure", {
    className: cx('md-swatch', className)
  }, /*#__PURE__*/React.createElement("div", {
    className: "md-swatch-chip",
    style: {
      background: color
    }
  }), /*#__PURE__*/React.createElement("figcaption", {
    className: "md-swatch-cap"
  }, /*#__PURE__*/React.createElement("div", {
    className: "md-swatch-name"
  }, name), /*#__PURE__*/React.createElement("div", {
    className: "md-swatch-value"
  }, value)));
}
Object.assign(__ds_scope, { Swatch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Swatch.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Dialog.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
let seq = 0;
function Dialog({
  open,
  onClose,
  title,
  description,
  actions,
  children,
  className
}) {
  const ref = React.useRef(null);
  const idRef = React.useRef('md-dialog-' + ++seq);
  React.useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  const id = idRef.current;
  return /*#__PURE__*/React.createElement("dialog", {
    ref: ref,
    className: cx('md-dialog', className),
    "aria-labelledby": id + '-t',
    "aria-describedby": description ? id + '-d' : undefined,
    onCancel: e => {
      e.preventDefault();
      if (onClose) onClose();
    },
    onClick: e => {
      if (e.target === ref.current && onClose) onClose();
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "md-dialog-body"
  }, /*#__PURE__*/React.createElement("h2", {
    id: id + '-t',
    className: "md-dialog-title"
  }, title), description ? /*#__PURE__*/React.createElement("p", {
    id: id + '-d',
    className: "md-dialog-desc"
  }, description) : null, children), actions ? /*#__PURE__*/React.createElement("div", {
    className: "md-dialog-actions"
  }, actions) : null);
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Notice.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
const TONE_ICON = {
  success: 'check',
  info: 'clock',
  warning: 'alert',
  danger: 'error'
};
function Notice({
  tone = 'info',
  title,
  action,
  children,
  className
}) {
  return /*#__PURE__*/React.createElement("div", {
    role: tone === 'danger' ? 'alert' : 'status',
    className: cx('md-notice', 'md-notice-' + tone, className)
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: TONE_ICON[tone],
    size: 16
  }), /*#__PURE__*/React.createElement("div", {
    className: "md-notice-main"
  }, title ? /*#__PURE__*/React.createElement("div", {
    className: "md-notice-title"
  }, title) : null, children ? /*#__PURE__*/React.createElement("div", null, children) : null), action || null);
}
Object.assign(__ds_scope, { Notice });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Notice.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Snackbar.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
function Snackbar({
  open = true,
  message,
  actionLabel,
  onAction,
  onClose,
  inline,
  className
}) {
  return /*#__PURE__*/React.createElement("div", {
    role: "status",
    "aria-live": "polite",
    className: cx('md-snack-region', inline && 'md-snack-inline')
  }, open ? /*#__PURE__*/React.createElement("div", {
    className: cx('md-snack', className)
  }, /*#__PURE__*/React.createElement("span", {
    className: "md-snack-msg"
  }, message), actionLabel ? /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "md-snack-action",
    onClick: onAction
  }, actionLabel) : null, onClose ? /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "md-snack-close",
    "aria-label": "Dismiss",
    onClick: onClose
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "close",
    size: 16
  })) : null) : null);
}
Object.assign(__ds_scope, { Snackbar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Snackbar.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const cx = (...a) => a.filter(Boolean).join(' ');
let seq = 0;
function Checkbox({
  label,
  hint,
  indeterminate,
  className,
  id: idProp,
  ...rest
}) {
  const ref = React.useRef(null);
  const idRef = React.useRef(idProp || 'md-check-' + ++seq);
  React.useEffect(() => {
    if (ref.current) ref.current.indeterminate = !!indeterminate;
  }, [indeterminate]);
  const id = idRef.current;
  return /*#__PURE__*/React.createElement("div", {
    className: cx('md-check', className)
  }, /*#__PURE__*/React.createElement("input", _extends({
    ref: ref,
    type: "checkbox",
    id: id,
    className: "md-check-box",
    "aria-describedby": hint ? id + '-hint' : undefined
  }, rest)), /*#__PURE__*/React.createElement("span", {
    className: "md-check-text"
  }, /*#__PURE__*/React.createElement("label", {
    htmlFor: id,
    className: "md-check-label"
  }, label), hint ? /*#__PURE__*/React.createElement("span", {
    id: id + '-hint',
    className: "md-check-hint"
  }, hint) : null));
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/Chip.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const cx = (...a) => a.filter(Boolean).join(' ');
function Chip({
  variant = 'filter',
  selected,
  icon,
  count,
  className,
  children,
  ...rest
}) {
  const filter = variant === 'filter';
  const lead = filter ? selected ? 'check' : icon : icon;
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-pressed": filter ? selected ? 'true' : 'false' : undefined
  }, rest, {
    className: cx('md-chip', filter && selected && 'md-chip-on', className)
  }), lead ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: lead,
    size: 16
  }) : null, /*#__PURE__*/React.createElement("span", null, children), count !== undefined ? /*#__PURE__*/React.createElement("span", {
    className: "md-chip-count"
  }, count) : null);
}
Object.assign(__ds_scope, { Chip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Chip.jsx", error: String((e && e.message) || e) }); }

// components/forms/SegmentedControl.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
function SegmentedControl({
  options = [],
  value,
  onChange,
  label,
  mono,
  className
}) {
  const refs = React.useRef([]);
  const cur = Math.max(0, options.indexOf(value));
  const move = e => {
    const k = e.key;
    let n = null;
    if (k === 'ArrowRight' || k === 'ArrowDown') n = (cur + 1) % options.length;else if (k === 'ArrowLeft' || k === 'ArrowUp') n = (cur - 1 + options.length) % options.length;else if (k === 'Home') n = 0;else if (k === 'End') n = options.length - 1;
    if (n === null) return;
    e.preventDefault();
    if (onChange) onChange(options[n]);
    if (refs.current[n]) refs.current[n].focus();
  };
  return /*#__PURE__*/React.createElement("div", {
    className: cx('md-seg', mono && 'md-seg-mono', className),
    role: "radiogroup",
    "aria-label": label,
    onKeyDown: move
  }, options.map((o, i) => {
    const on = i === cur;
    return /*#__PURE__*/React.createElement("button", {
      key: o,
      ref: el => {
        refs.current[i] = el;
      },
      type: "button",
      role: "radio",
      "aria-checked": on ? 'true' : 'false',
      tabIndex: on ? 0 : -1,
      className: cx('md-seg-opt', on && 'md-seg-on'),
      onClick: onChange ? () => onChange(o) : undefined
    }, o);
  }));
}
Object.assign(__ds_scope, { SegmentedControl });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/SegmentedControl.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
let seq = 0;
function Switch({
  label,
  checked,
  defaultChecked,
  onChange,
  disabled,
  className
}) {
  const [inner, setInner] = React.useState(!!defaultChecked);
  const on = checked === undefined ? inner : !!checked;
  const idRef = React.useRef('md-switch-' + ++seq);
  const flip = () => {
    if (disabled) return;
    if (checked === undefined) setInner(!on);
    if (onChange) onChange(!on);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: cx('md-switch-row', className)
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    role: "switch",
    "aria-checked": on ? 'true' : 'false',
    "aria-labelledby": idRef.current,
    disabled: disabled,
    className: cx('md-switch', on && 'md-switch-on'),
    onClick: flip
  }, /*#__PURE__*/React.createElement("span", {
    className: "md-switch-thumb"
  })), /*#__PURE__*/React.createElement("span", {
    id: idRef.current,
    className: "md-switch-label",
    onClick: flip
  }, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// components/forms/TextField.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const cx = (...a) => a.filter(Boolean).join(' ');
let fieldSeq = 0;
function TextField({
  label,
  hint,
  error,
  mono,
  unit,
  className,
  id: idProp,
  ...rest
}) {
  const ref = React.useRef(null);
  if (ref.current === null) ref.current = idProp || 'md-field-' + ++fieldSeq;
  const id = ref.current;
  const noteId = error || hint ? id + '-note' : undefined;
  const unitId = unit ? id + '-unit' : undefined;
  const described = [unitId, noteId].filter(Boolean).join(' ') || undefined;
  return /*#__PURE__*/React.createElement("div", {
    className: cx('md-field', error && 'md-field-error', className)
  }, /*#__PURE__*/React.createElement("label", {
    className: "md-field-label",
    htmlFor: id
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "md-field-box"
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "text"
  }, rest, {
    id: id,
    className: cx('md-input', mono && 'md-input-mono', unit && 'md-input-unit'),
    "aria-invalid": error ? 'true' : undefined,
    "aria-describedby": described
  })), unit ? /*#__PURE__*/React.createElement("span", {
    className: "md-field-unit",
    id: unitId
  }, unit) : null), error ? /*#__PURE__*/React.createElement("p", {
    className: "md-field-note",
    id: noteId
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "error",
    size: 14,
    className: "md-field-note-icon"
  }), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
    className: "md-sr-only"
  }, "Error: "), error)) : hint ? /*#__PURE__*/React.createElement("p", {
    className: "md-field-note",
    id: noteId
  }, hint) : null);
}
Object.assign(__ds_scope, { TextField });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/TextField.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
const cx = (...a) => a.filter(Boolean).join(' ');
function Tabs({
  tabs = [],
  value,
  onChange,
  label,
  idPrefix = 'md-tabs',
  className
}) {
  const refs = React.useRef([]);
  const cur = Math.max(0, tabs.findIndex(t => t.id === value));
  const key = e => {
    let n = null;
    if (e.key === 'ArrowRight') n = (cur + 1) % tabs.length;else if (e.key === 'ArrowLeft') n = (cur - 1 + tabs.length) % tabs.length;else if (e.key === 'Home') n = 0;else if (e.key === 'End') n = tabs.length - 1;
    if (n === null) return;
    e.preventDefault();
    if (onChange) onChange(tabs[n].id);
    if (refs.current[n]) refs.current[n].focus();
  };
  return /*#__PURE__*/React.createElement("div", {
    role: "tablist",
    "aria-label": label,
    className: cx('md-tabs', className),
    onKeyDown: key
  }, tabs.map((t, i) => {
    const on = i === cur;
    return /*#__PURE__*/React.createElement("button", {
      key: t.id,
      ref: el => {
        refs.current[i] = el;
      },
      type: "button",
      role: "tab",
      id: idPrefix + '-tab-' + t.id,
      "aria-selected": on ? 'true' : 'false',
      "aria-controls": idPrefix + '-panel-' + t.id,
      tabIndex: on ? 0 : -1,
      className: cx('md-tab', on && 'md-tab-on'),
      onClick: () => onChange && onChange(t.id)
    }, /*#__PURE__*/React.createElement("span", null, t.label), t.count !== undefined ? /*#__PURE__*/React.createElement("span", {
      className: "md-tab-count"
    }, t.count) : null);
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// ui_kits/style-guide/ComponentGallery.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const {
  Button,
  Badge,
  Card,
  SectionHeader,
  TextField,
  SegmentedControl,
  Progress,
  Readout,
  ListRow,
  Chart,
  Swatch,
  Checkbox,
  Switch,
  Chip,
  Tabs,
  Dialog,
  Snackbar,
  Notice
} = window.MyDefaultDesignSystem_f28e8c;
function ChipsDemo() {
  const [f, setF] = React.useState('All');
  return /*#__PURE__*/React.createElement("div", {
    className: "md-stage",
    role: "group",
    "aria-label": "Filter files"
  }, [['All', 5], ['Folders', 2], ['Files', 3]].map(([l, n]) => /*#__PURE__*/React.createElement(Chip, {
    key: l,
    selected: f === l,
    count: n,
    onClick: () => setF(l)
  }, l)), /*#__PURE__*/React.createElement(Chip, {
    variant: "assist",
    icon: "download"
  }, "Export CSV"));
}
function TabsDemo() {
  const [t, setT] = React.useState('files');
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 'var(--space-5)'
    }
  }, /*#__PURE__*/React.createElement(Tabs, {
    label: "Project",
    value: t,
    onChange: setT,
    idPrefix: "sg",
    tabs: [{
      id: 'files',
      label: 'Files',
      count: 5
    }, {
      id: 'activity',
      label: 'Activity'
    }, {
      id: 'settings',
      label: 'Settings'
    }]
  }));
}
function DialogDemo() {
  const [o, setO] = React.useState(false);
  const [s, setS] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    className: "md-stage"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "danger",
    onClick: () => setO(true)
  }, "Delete files"), /*#__PURE__*/React.createElement(Snackbar, {
    inline: true,
    open: s,
    message: "2 files deleted",
    actionLabel: "Undo",
    onAction: () => setS(false),
    onClose: () => setS(false)
  }), /*#__PURE__*/React.createElement(Dialog, {
    open: o,
    onClose: () => setO(false),
    title: "Delete 2 files?",
    description: "You can't undo this.",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      onClick: () => setO(false)
    }, "Cancel"), /*#__PURE__*/React.createElement(Button, {
      variant: "danger",
      onClick: () => {
        setO(false);
        setS(true);
      }
    }, "Delete files"))
  }));
}
function ControlledSeg(p) {
  const [v, setV] = React.useState(p.value);
  return /*#__PURE__*/React.createElement(SegmentedControl, _extends({}, p, {
    value: v,
    onChange: setV
  }));
}
function Rows() {
  const [sel, setSel] = React.useState(0);
  const rows = [{
    title: 'report_2026-07.csv',
    values: ['Jul 15, 2026 at 10:18', '2.4 MB', 'CSV document']
  }, {
    title: 'contacts_export.csv',
    values: ['Jul 15, 2026 at 11:02', '840 KB', 'CSV document']
  }, {
    icon: 'folder',
    title: 'Archive',
    values: ['Jul 16, 2026 at 09:40', '--', 'Folder']
  }];
  const cols = '20px minmax(0,1fr) 160px 72px 112px 0px';
  return /*#__PURE__*/React.createElement(Card, {
    padding: "none",
    title: "Files"
  }, /*#__PURE__*/React.createElement("div", {
    role: "grid",
    "aria-label": "Files"
  }, /*#__PURE__*/React.createElement("div", {
    role: "row",
    style: {
      display: 'grid',
      gridTemplateColumns: cols,
      alignItems: 'center',
      gap: 12,
      padding: '8px 16px',
      borderBottom: '1px solid var(--border)',
      fontSize: 12,
      lineHeight: '16px',
      fontWeight: 500,
      color: 'var(--ink-muted)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    role: "columnheader"
  }, /*#__PURE__*/React.createElement("span", {
    className: "md-sr-only"
  }, "Type")), /*#__PURE__*/React.createElement("span", {
    role: "columnheader"
  }, "Name"), /*#__PURE__*/React.createElement("span", {
    role: "columnheader",
    style: {
      textAlign: 'right'
    }
  }, "Date modified"), /*#__PURE__*/React.createElement("span", {
    role: "columnheader",
    style: {
      textAlign: 'right'
    }
  }, "Size"), /*#__PURE__*/React.createElement("span", {
    role: "columnheader",
    style: {
      textAlign: 'right'
    }
  }, "Kind"), /*#__PURE__*/React.createElement("span", {
    role: "columnheader"
  }, /*#__PURE__*/React.createElement("span", {
    className: "md-sr-only"
  }, "Status"))), rows.map((r, i) => /*#__PURE__*/React.createElement(ListRow, _extends({
    key: i
  }, r, {
    style: {
      gridTemplateColumns: cols
    },
    selected: sel === i,
    onClick: () => setSel(i)
  })))));
}
const GALLERY = {
  Button: ['Buttons start an action, and the secondary variant is the default.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    icon: "plus"
  }, "New project"), /*#__PURE__*/React.createElement(Button, {
    icon: "download"
  }, "Export CSV"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost"
  }, "Cancel"), /*#__PURE__*/React.createElement(Button, {
    variant: "danger"
  }, "Delete project"), /*#__PURE__*/React.createElement(Button, {
    disabled: true
  }, "Archive"), /*#__PURE__*/React.createElement(Button, {
    icon: "close",
    iconOnly: true,
    "aria-label": "Close"
  }))],
  Badge: ['A badge shows one or two words of type or status next to an item.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage"
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "success",
    icon: "live"
  }, "Live"), /*#__PURE__*/React.createElement(Badge, {
    icon: "loader"
  }, "Connecting"), /*#__PURE__*/React.createElement(Badge, {
    icon: "refresh"
  }, "Reconnecting"), /*#__PURE__*/React.createElement(Badge, {
    icon: "pause"
  }, "Paused"), /*#__PURE__*/React.createElement(Badge, {
    tone: "brand"
  }, "Selected"), /*#__PURE__*/React.createElement(Badge, {
    tone: "success"
  }, "Complete"), /*#__PURE__*/React.createElement(Badge, {
    tone: "info"
  }, "Scheduled"), /*#__PURE__*/React.createElement(Badge, {
    tone: "warning"
  }, "Needs review"), /*#__PURE__*/React.createElement(Badge, {
    tone: "danger"
  }, "Failed"))],
  Card: ['A card groups related content on the page ground.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage",
    style: {
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement(Card, {
    title: "Project details",
    style: {
      width: 300
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 'var(--space-4)'
    }
  }, /*#__PURE__*/React.createElement(Readout, {
    label: "Created",
    value: "2026-07-15"
  }), /*#__PURE__*/React.createElement(Readout, {
    label: "Members",
    value: "8"
  }), /*#__PURE__*/React.createElement(Readout, {
    label: "Storage",
    value: "2.4",
    unit: "GB"
  }), /*#__PURE__*/React.createElement(Readout, {
    label: "Open tasks",
    value: "41"
  }))), /*#__PURE__*/React.createElement(Card, {
    title: "Notifications",
    elevation: "raised",
    action: /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm"
    }, "Edit"),
    style: {
      width: 300
    }
  }, /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: 13,
      lineHeight: '20px',
      color: 'var(--ink-secondary)'
    }
  }, "You get an email when someone mentions you or assigns you a task.")))],
  SectionHeader: ['A section header opens a section of a document page.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage-col"
  }, /*#__PURE__*/React.createElement(SectionHeader, {
    title: "Color"
  }, "A clear blue brand on quiet neutrals, with four status colors."))],
  TextField: ['A text field takes one line of input with a label above it.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage",
    style: {
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement(TextField, {
    label: "Project name",
    placeholder: "Quarterly report"
  }), /*#__PURE__*/React.createElement(TextField, {
    label: "Timeout",
    defaultValue: "30",
    unit: "s",
    hint: "Between 5 and 120 seconds."
  }), /*#__PURE__*/React.createElement(TextField, {
    label: "Start date",
    defaultValue: "2026-13-01",
    error: "Use a date in the format YYYY-MM-DD.",
    mono: true
  }))],
  SegmentedControl: ['A segmented control picks one option from two to five short choices.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage"
  }, /*#__PURE__*/React.createElement(ControlledSeg, {
    label: "View",
    options: ['Day', 'Week', 'Month'],
    value: "Week"
  }), /*#__PURE__*/React.createElement(ControlledSeg, {
    label: "Zoom",
    options: ['50%', '100%', '200%'],
    value: "100%"
  }))],
  Progress: ['A progress bar shows how much of a task or a limit is complete.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage",
    style: {
      gap: 'var(--space-8)'
    }
  }, /*#__PURE__*/React.createElement(Progress, {
    label: "Upload",
    value: 0.62,
    showValue: true
  }), /*#__PURE__*/React.createElement(Progress, {
    label: "Storage used",
    value: 0.91,
    tone: "warning",
    showValue: true
  }))],
  Readout: ['A readout shows one value with a short field label under it.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage",
    style: {
      gap: 'var(--space-8)'
    }
  }, /*#__PURE__*/React.createElement(Readout, {
    label: "Requests",
    value: "1,284",
    size: "lg"
  }), /*#__PURE__*/React.createElement(Readout, {
    label: "Median latency",
    value: "42",
    unit: "ms"
  }), /*#__PURE__*/React.createElement(Readout, {
    label: "Error rate",
    value: "0.3",
    unit: "%"
  }), /*#__PURE__*/React.createElement(Readout, {
    label: "Last deploy",
    value: "2026-07-15 10:18"
  }))],
  Checkbox: ['A checkbox picks any number of independent options.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage-col"
  }, /*#__PURE__*/React.createElement(Checkbox, {
    label: "Email me when an export finishes",
    defaultChecked: true
  }), /*#__PURE__*/React.createElement(Checkbox, {
    label: "All projects",
    indeterminate: true
  }), /*#__PURE__*/React.createElement(Checkbox, {
    label: "Include archived",
    hint: "Adds 3 projects"
  }))],
  Switch: ['A switch turns one setting on or off immediately.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage"
  }, /*#__PURE__*/React.createElement(Switch, {
    label: "Auto-refresh",
    defaultChecked: true
  }), /*#__PURE__*/React.createElement(Switch, {
    label: "Compact rows"
  }), /*#__PURE__*/React.createElement(Switch, {
    label: "Sync",
    disabled: true
  }))],
  Chip: ['Filter chips toggle a filter; assist chips run a quick action.', () => /*#__PURE__*/React.createElement(ChipsDemo, null)],
  Tabs: ['Tabs switch between views of the same object.', () => /*#__PURE__*/React.createElement(TabsDemo, null)],
  Notice: ['A notice is a persistent inline message on a tone container.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage-col"
  }, /*#__PURE__*/React.createElement(Notice, {
    tone: "info",
    title: "Next sync runs at 14:00"
  }), /*#__PURE__*/React.createElement(Notice, {
    tone: "warning",
    title: "3 rows have missing dates"
  }, "They are skipped in the chart."), /*#__PURE__*/React.createElement(Notice, {
    tone: "danger",
    title: "Upload failed"
  }, "Check the file format and try again."))],
  Dialog: ['A dialog confirms a consequential action; a snackbar confirms it happened.', () => /*#__PURE__*/React.createElement(DialogDemo, null)],
  ListRow: ['A list row shows one item with an icon, a name and its details.', () => /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 'var(--space-5)'
    }
  }, /*#__PURE__*/React.createElement(Rows, null))],
  Chart: ['A chart draws one numeric series as a line.', () => /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 'var(--space-5)'
    }
  }, /*#__PURE__*/React.createElement(Card, {
    style: {
      width: 560
    }
  }, /*#__PURE__*/React.createElement(Chart, {
    title: "Requests, last 7 days",
    value: "8,912",
    data: [1080, 1190, 1150, 1420, 1310, 1290, 1472],
    height: 160,
    xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  })))],
  Swatch: ['A swatch documents one color with its name and value.', () => /*#__PURE__*/React.createElement("div", {
    className: "md-stage"
  }, /*#__PURE__*/React.createElement(Swatch, {
    name: "Blue 500",
    value: "#2954B5",
    color: "var(--blue-500)"
  }), /*#__PURE__*/React.createElement(Swatch, {
    name: "Green 500",
    value: "#367F50",
    color: "var(--green-500)"
  }), /*#__PURE__*/React.createElement(Swatch, {
    name: "Orange 500",
    value: "#C24E00",
    color: "var(--orange-500)"
  }))]
};
function ComponentGallery() {
  return Object.keys(GALLERY).map(n => /*#__PURE__*/React.createElement("div", {
    className: "sg-comp",
    key: n
  }, /*#__PURE__*/React.createElement("div", {
    className: "sg-comp-head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "section-heading"
  }, n), /*#__PURE__*/React.createElement("div", {
    className: "body-sm",
    style: {
      color: 'var(--ink-secondary)'
    }
  }, GALLERY[n][0])), /*#__PURE__*/React.createElement("div", {
    className: "sg-comp-body"
  }, GALLERY[n][1]())));
}
window.ComponentGallery = ComponentGallery;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/style-guide/ComponentGallery.jsx", error: String((e && e.message) || e) }); }

// ui_kits/style-guide/StyleGuide.jsx
try { (() => {
const {
  SectionHeader: SGSectionHeader,
  SegmentedControl: SGSeg
} = window.MyDefaultDesignSystem_f28e8c;
const SG_GROUPS = [['Surface', n => n.startsWith('surface-')], ['Text', n => n.startsWith('ink') || n === 'link' || n === 'on-brand'], ['Border', n => n.startsWith('border')], ['Brand', n => n.startsWith('brand')], ['Status roles', n => /^(on-)?(success|info|warning|danger)$/.test(n) || n === 'neutral'], ['Status containers', n => /^(on-)?(success|info|warning|danger)-container$/.test(n)]];
const SG_PRIM = [['Blue', 'blue-'], ['Night', 'night-'], ['Status', /^(green|orange|red|gray)-/]];
function sgResolve(v, prim) {
  const m = /^\{(.+)\}$/.exec(v);
  return m ? prim[m[1]] : v;
}
function Tok({
  c,
  prim
}) {
  const themed = typeof c.value !== 'string';
  const L = themed ? sgResolve(c.value.light, prim) : c.value;
  const Dk = themed ? sgResolve(c.value.dark, prim) : null;
  return /*#__PURE__*/React.createElement("div", {
    className: "sg-tok"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sg-chip"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      background: L
    }
  }), themed ? /*#__PURE__*/React.createElement("span", {
    style: {
      background: Dk
    }
  }) : null), /*#__PURE__*/React.createElement("div", {
    className: "sg-tok-body"
  }, /*#__PURE__*/React.createElement("div", {
    className: "control-label"
  }, c.name), /*#__PURE__*/React.createElement("div", {
    className: "value-sm sg-vals"
  }, themed ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", null, L), /*#__PURE__*/React.createElement("span", null, Dk)) : /*#__PURE__*/React.createElement("span", null, L)), /*#__PURE__*/React.createElement("div", {
    className: "sg-note"
  }, c.usage)));
}
function StyleGuide({
  D
}) {
  const [theme, setTheme] = React.useState('light');
  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);
  const colors = D.color.tokens;
  const primList = colors.filter(c => typeof c.value === 'string');
  const sem = colors.filter(c => typeof c.value !== 'string');
  const prim = Object.fromEntries(primList.map(c => [c.name, c.value]));
  return /*#__PURE__*/React.createElement("div", {
    className: "sg"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sg-top"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "eyebrow",
    style: {
      color: 'var(--ink-secondary)'
    }
  }, "Style guide"), /*#__PURE__*/React.createElement("h1", {
    className: "page-title",
    style: {
      margin: '4px 0 0'
    }
  }, "My Default"), /*#__PURE__*/React.createElement("p", {
    className: "body sg-intro"
  }, "A clear, precise system for data-heavy apps. Every color, type style, space, radius and component in one page.")), /*#__PURE__*/React.createElement(SGSeg, {
    label: "Theme",
    options: ['Light', 'Dark'],
    value: theme === 'light' ? 'Light' : 'Dark',
    onChange: o => setTheme(o.toLowerCase())
  })), /*#__PURE__*/React.createElement("div", {
    className: "sg-block"
  }, /*#__PURE__*/React.createElement(SGSectionHeader, {
    title: "Color"
  }, "Build with semantic tokens. Each one shows its light value on the left and its dark value on the right. Primitives feed the semantic tokens; don't use them directly."), SG_GROUPS.map(([g, f]) => /*#__PURE__*/React.createElement("div", {
    key: g
  }, /*#__PURE__*/React.createElement("div", {
    className: "section-heading sg-sub"
  }, g), /*#__PURE__*/React.createElement("div", {
    className: "sg-grid"
  }, sem.filter(c => f(c.name)).map(c => /*#__PURE__*/React.createElement(Tok, {
    key: c.name,
    c: c,
    prim: prim
  }))))), /*#__PURE__*/React.createElement("div", {
    className: "section-heading sg-sub sg-sub-major"
  }, "Primitives"), SG_PRIM.map(([g, p]) => /*#__PURE__*/React.createElement("div", {
    key: g
  }, /*#__PURE__*/React.createElement("div", {
    className: "sg-sub-minor"
  }, g), /*#__PURE__*/React.createElement("div", {
    className: "sg-grid"
  }, primList.filter(c => typeof p === 'string' ? c.name.startsWith(p) : p.test(c.name)).map(c => /*#__PURE__*/React.createElement(Tok, {
    key: c.name,
    c: c,
    prim: prim
  })))))), /*#__PURE__*/React.createElement("div", {
    className: "sg-block"
  }, /*#__PURE__*/React.createElement(SGSectionHeader, {
    title: "Type"
  }, "Red Hat Display for the wordmark and major titles, Libre Franklin for everything else with tabular figures for numbers, IBM Plex Mono for identifiers."), D.type.groups.map(g => /*#__PURE__*/React.createElement("div", {
    key: g.name
  }, /*#__PURE__*/React.createElement("div", {
    className: "section-heading sg-sub"
  }, g.name), g.styles.map(st => /*#__PURE__*/React.createElement("div", {
    className: "sg-type",
    key: st.name
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "control-label"
  }, st.name), /*#__PURE__*/React.createElement("div", {
    className: "value-sm",
    style: {
      color: 'var(--ink-secondary)'
    }
  }, st.fontSize + ' / ' + st.lineHeight + ' / ' + st.fontWeight)), /*#__PURE__*/React.createElement("div", {
    className: st.name,
    style: {
      color: 'var(--ink)'
    }
  }, st.sample)))))), /*#__PURE__*/React.createElement("div", {
    className: "sg-block"
  }, /*#__PURE__*/React.createElement(SGSectionHeader, {
    title: "Space, radius and shadow"
  }, "A 4px spacing base, small corners, and hairline rings instead of blurred shadows."), /*#__PURE__*/React.createElement("div", {
    className: "section-heading sg-sub"
  }, "Spacing"), D.spacing.tokens.map(sp => /*#__PURE__*/React.createElement("div", {
    className: "sg-row",
    key: sp.name
  }, /*#__PURE__*/React.createElement("span", {
    className: "control-label"
  }, sp.name), /*#__PURE__*/React.createElement("span", {
    className: "value-sm"
  }, sp.value), /*#__PURE__*/React.createElement("div", {
    className: "sg-bar",
    style: {
      width: sp.value
    }
  }))), /*#__PURE__*/React.createElement("div", {
    className: "section-heading sg-sub"
  }, "Radius"), /*#__PURE__*/React.createElement("div", {
    className: "sg-grid"
  }, D.radius.tokens.map(r => /*#__PURE__*/React.createElement("div", {
    key: r.name,
    className: "sg-tok",
    style: {
      padding: 'var(--space-4)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 56,
      background: 'var(--surface-sunken)',
      border: '1px solid var(--border-strong)',
      borderRadius: r.value
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "control-label",
    style: {
      marginTop: 8
    }
  }, r.name + ' ' + r.value), /*#__PURE__*/React.createElement("div", {
    className: "sg-note"
  }, r.usage)))), /*#__PURE__*/React.createElement("div", {
    className: "section-heading sg-sub"
  }, "Shadow"), /*#__PURE__*/React.createElement("div", {
    className: "sg-grid"
  }, D.shadow.tokens.map(sh => /*#__PURE__*/React.createElement("div", {
    key: sh.name,
    style: {
      background: 'var(--surface-card)',
      borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-4)',
      boxShadow: 'var(--' + sh.name + ')'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "control-label"
  }, sh.name), /*#__PURE__*/React.createElement("div", {
    className: "sg-note"
  }, sh.usage))))), /*#__PURE__*/React.createElement("div", {
    className: "sg-block"
  }, /*#__PURE__*/React.createElement(SGSectionHeader, {
    title: "Components"
  }, "Each component with its main states. The guidelines are in each component README."), /*#__PURE__*/React.createElement(window.ComponentGallery, null)));
}
window.StyleGuide = StyleGuide;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/style-guide/StyleGuide.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.SectionHeader = __ds_scope.SectionHeader;

__ds_ns.Chart = __ds_scope.Chart;

__ds_ns.ListRow = __ds_scope.ListRow;

__ds_ns.Progress = __ds_scope.Progress;

__ds_ns.Readout = __ds_scope.Readout;

__ds_ns.Swatch = __ds_scope.Swatch;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.Notice = __ds_scope.Notice;

__ds_ns.Snackbar = __ds_scope.Snackbar;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Chip = __ds_scope.Chip;

__ds_ns.SegmentedControl = __ds_scope.SegmentedControl;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.TextField = __ds_scope.TextField;

__ds_ns.Tabs = __ds_scope.Tabs;

})();
