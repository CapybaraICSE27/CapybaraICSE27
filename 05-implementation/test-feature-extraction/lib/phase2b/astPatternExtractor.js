"use strict";

/**
 * AST-derived RQ3 pattern fields (locator / wait / assertion-sync / workflow).
 * Used during Phase 2B; Python 2D prefers *_ast fields with regex fallback.
 */

const { Node } = require("ts-morph");

const LOCATOR_APIS = {
  getByRole: "role_or_accessibility",
  findByRole: "role_or_accessibility",
  getByLabel: "label_or_form_affordance",
  findByLabel: "label_or_form_affordance",
  findByLabelText: "label_or_form_affordance",
  getByPlaceholder: "placeholder_or_alt_title",
  findByPlaceholderText: "placeholder_or_alt_title",
  getByAltText: "placeholder_or_alt_title",
  getByTitle: "placeholder_or_alt_title",
  findByTitle: "placeholder_or_alt_title",
  getByText: "text_content",
  findByText: "text_content",
  getByTestId: "test_id_or_data_contract",
  findByTestId: "test_id_or_data_contract",
  getByDataCy: "test_id_or_data_contract",
  getByCls: "css_selector",
  findByAttribute: "css_selector",
  contains: "text_content",
};

const UI_TERMINAL_ACTIONS = new Set([
  "click", "dblclick", "fill", "type", "press", "clear", "check", "uncheck",
  "hover", "selectOption", "setInputFiles", "tap", "focus", "blur",
  "setValue", "addValue", "typeText", "navigateTo",
]);

const RETRYABLE_ASSERT_MATCHERS = new Set([
  "tobevisible", "tobehidden", "tocontaintext", "tohavetext", "tohaveurl",
  "tohaveattribute", "tohavevalue", "tohavecss", "tohaveclass",
  "tobedisplayed", "tobeexisting", "tobeclickable", "tobeenabled",
  "tobedisabled", "tobechecked", "tobeselected", "tobefocused",
  "tobeeditable", "tobeattached", "tobeempty", "tobeinviewport",
  "tohaveaccessibledescription", "tohaveaccessiblename", "tohavecount",
  "tohaveid", "tohavejsproperty", "tohaverole", "tohavescreenshot",
  "tohavetitle", "tohavevalues",
]);

function getCallName(call) {
  const expr = call.getExpression();
  if (Node.isPropertyAccessExpression(expr)) return expr.getName();
  if (Node.isIdentifier(expr)) return expr.getText();
  return expr.getText();
}

/** Outermost call in a chained expression (e.g. page.getByRole(...).click). */
function getOutermostCall(node) {
  let cur = node;
  while (cur && Node.isAwaitExpression(cur)) cur = cur.getExpression();
  if (Node.isPropertyAccessExpression(cur) && Node.isCallExpression(cur.getParent())) {
    cur = cur.getParent();
  }
  if (!Node.isCallExpression(cur)) return null;

  let top = cur;
  for (;;) {
    const parent = top.getParent();
    if (parent && Node.isPropertyAccessExpression(parent)) {
      const gp = parent.getParent();
      if (gp && Node.isCallExpression(gp)) {
        top = gp;
        continue;
      }
    }
    break;
  }
  return top;
}

function extractCallChainFromCall(call) {
  const chain = [];
  let current = call;
  while (current && Node.isCallExpression(current)) {
    chain.unshift(getCallName(current));
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const receiver = expr.getExpression();
    if (Node.isCallExpression(receiver)) {
      current = receiver;
    } else {
      chain.unshift(receiver.getText());
      break;
    }
  }
  return chain;
}

function getFirstStringArg(call) {
  const args = call.getArguments();
  if (!args.length) return null;
  const a0 = args[0];
  if (Node.isStringLiteral(a0)) return a0.getLiteralText();
  if (Node.isNoSubstitutionTemplateLiteral(a0)) return a0.getLiteralText();
  if (Node.isTemplateExpression(a0)) return a0.getText();
  return null;
}

function getFirstArg(call) {
  const args = call?.getArguments?.() || [];
  return args.length ? args[0] : null;
}

function selectorValueOrigin(arg) {
  if (!arg) return "none";
  if (Node.isStringLiteral(arg) || Node.isNoSubstitutionTemplateLiteral(arg) || Node.isNumericLiteral(arg)) {
    return "inline_literal";
  }
  if (Node.isTemplateExpression(arg)) return "computed";
  if (Node.isIdentifier(arg)) return "identifier";
  if (Node.isPropertyAccessExpression(arg) || Node.isElementAccessExpression?.(arg)) return "member_path";
  if (Node.isCallExpression(arg)) return "call_expression";
  if (Node.isBinaryExpression(arg) || Node.isConditionalExpression?.(arg)) return "computed";
  return "computed";
}

function classifySelectorLiteralKind(literal) {
  if (!literal) return "unknown";
  const s = String(literal);
  const low = s.toLowerCase();
  if (low.startsWith("@")) return "cypress_alias_reference";
  if (low.startsWith("role=") || low.startsWith("role:")) return "role";
  if (low.startsWith("text=") || low.startsWith("text:")) return "text";
  if (low.startsWith("xpath=") || low.startsWith("//") || low.startsWith("(//")) return "xpath";
  const attrChannel = selectorChannelFromAttributeLiteral(s);
  if (attrChannel) return attrChannel;
  if (/\brole\s*=\s*['"][^'"]+['"]/i.test(s)) return "role";
  if (/data-(?:testid|test-id|test|cy|qa|pw|test-subj)|datacy/i.test(s)) return "test_id";
  if (/data-[a-z0-9_-]+/i.test(s)) return "data_attribute";
  if (s.startsWith("#")) return "id";
  if (/(^|[\s>+~])\.[A-Za-z0-9_-]+/.test(s)) return "class";
  if (s.startsWith(".") && !s.includes(" ")) return "class";
  if (/>\s*|:nth-|>>/.test(s)) return "css_structural";
  if (/[\s>+~]/.test(s)) return "css_compound";
  return "unknown";
}

function selectorChannelFromAttributeLiteral(literal) {
  const s = String(literal || "");
  if (/\[\s*(?:data-testid|data-test-id|data-test|data-cy|data-qa|data-pw|data-test-subj)\b/i.test(s)) {
    return "test_id";
  }
  if (/\[\s*placeholder\b/i.test(s)) return "placeholder";
  if (/\[\s*title\b/i.test(s)) return "title";
  if (/\[\s*alt\b/i.test(s)) return "alt";
  if (/\[\s*(?:aria-label|aria-labelledby|label)\b/i.test(s)) return "label";
  if (/\[\s*role\b/i.test(s)) return "role";
  if (/\[\s*data-[a-z0-9_-]+\b/i.test(s)) return "data_attribute";
  return "";
}

function strategyFromSelectorChannel(channel) {
  switch (channel) {
    case "test_id":
      return "test_id_or_data_contract";
    case "role":
      return "role_or_accessibility";
    case "label":
      return "label_or_form_affordance";
    case "placeholder":
    case "title":
    case "alt":
      return "placeholder_or_alt_title";
    case "text":
      return "text_content";
    case "xpath":
      return "xpath_selector";
    default:
      return "";
  }
}

function classifyApiLocatorArgKind(apiName, call, selectorLiteral) {
  const api = apiName || "";
  if (api === "getByRole" || api === "findByRole") return "role";
  if (api === "getByText" || api === "findByText" || api === "contains") return "text";
  if (api === "getByTestId" || api === "findByTestId" || api === "getByDataCy") return "test_id";
  if (api === "getByCls") return "class";
  if (api === "getByLabel" || api === "findByLabel" || api === "findByLabelText") return "label";
  if (api === "getByPlaceholder" || api === "findByPlaceholderText") return "placeholder";
  if (api === "getByAltText") return "alt";
  if (api === "getByTitle" || api === "findByTitle") return "title";
  if (api === "xpath") return "xpath";
  if (api === "findByAttribute") {
    const attr = getFirstStringArg(call);
    if (attr && /^(aria-label|label)$/i.test(attr)) return "label";
    if (attr && /^(data-cy|data-testid|data-test)$/i.test(attr)) return "test_id";
    if (attr && /^data-/i.test(attr)) return "data_attribute";
    if (attr && /^role$/i.test(attr)) return "role";
    if (attr && /^placeholder$/i.test(attr)) return "placeholder";
  }
  return classifySelectorLiteralKind(selectorLiteral);
}

function strategyFromAttributeCall(call) {
  const attr = getFirstStringArg(call);
  if (!attr) return "css_selector";
  const low = attr.toLowerCase();
  if (low === "aria-label" || low === "label") return "label_or_form_affordance";
  if (low === "data-cy" || low === "data-testid" || low === "data-test" || low.startsWith("data-")) {
    return "test_id_or_data_contract";
  }
  if (low === "role") return "role_or_accessibility";
  if (low === "placeholder") return "placeholder_or_alt_title";
  return "css_selector";
}

function isAssertionValueCheckCall(call) {
  const terminal = (getCallName(call) || "").toLowerCase();
  if (!["contains", "contain", "includes", "include"].includes(terminal)) return false;
  let current = call;
  for (let depth = 0; depth < 8; depth++) {
    if (!current || !Node.isCallExpression(current)) break;
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const recv = expr.getExpression();
    if (Node.isCallExpression(recv)) {
      const inner = getCallName(recv);
      if (inner === "expect" || inner === "assert") return true;
      current = recv;
      continue;
    }
    const recvText = recv.getText();
    if (/^expect\b/.test(recvText) || /^assert\b/.test(recvText)) return true;
    break;
  }
  return false;
}

function strategyFromLocatorApi(apiName, selectorLiteral, call) {
  if (apiName === "findByAttribute" && call) {
    return strategyFromAttributeCall(call);
  }
  if (apiName === "xpath") return "xpath_selector";
  if (apiName && LOCATOR_APIS[apiName]) return LOCATOR_APIS[apiName];
  if (apiName === "locator" || apiName === "get") {
    const kind = classifySelectorLiteralKind(selectorLiteral);
    const channelStrategy = strategyFromSelectorChannel(kind);
    if (channelStrategy) return channelStrategy;
    if (kind === "xpath") return "xpath_selector";
    if (kind === "test_id" || kind === "data_attribute") return "test_id_or_data_contract";
    if (kind === "text") return "text_content";
    return "css_selector";
  }
  if (apiName === "Selector") return "framework_selector_object";
  if (apiName === "$" || apiName === "$$") return "css_selector";
  return null;
}

function hasChainedRefinement(call) {
  let depth = 0;
  let current = call;
  while (current && Node.isCallExpression(current)) {
    const name = getCallName(current);
    if (["filter", "nth", "first", "last", "and", "or", "eq"].includes(name)) depth += 1;
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const receiver = expr.getExpression();
    if (Node.isCallExpression(receiver)) current = receiver;
    else break;
  }
  return depth > 0;
}

function hasPositionalRefinement(call) {
  let current = call;
  while (current && Node.isCallExpression(current)) {
    const name = getCallName(current);
    if (["nth", "first", "last", "eq"].includes(name)) return true;
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const receiver = expr.getExpression();
    if (Node.isCallExpression(receiver)) current = receiver;
    else break;
  }
  return false;
}

function findLocatorSubCall(call) {
  let current = call;
  while (current && Node.isCallExpression(current)) {
    if (isAssertionValueCheckCall(current)) return null;
    const name = getCallName(current);
    if (LOCATOR_APIS[name] || name === "xpath" || name === "locator" || name === "get" || name === "Selector" || name === "$") {
      return { call: current, apiName: name };
    }
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const receiver = expr.getExpression();
    if (Node.isCallExpression(receiver)) current = receiver;
    else break;
  }
  return null;
}

function pageObjectMediatedLocator(chain, terminal) {
  return {
    callee_chain: chain,
    terminal_action_ast: terminal,
    locator_api_ast: "",
    locator_strategy_ast: "page_object_mediated",
    locator_composition_ast: "page_object_mediated",
    selector_literal_ast: "",
    selector_literal_kind_ast: "unknown",
    selector_channel_ast: "unknown",
    selector_value_origin_ast: "none",
    has_positional_refinement_ast: false,
    has_chained_refinement_ast: false,
    ast_confidence: "medium",
  };
}

function extractLocatorInfo(callNode, framework, ctx = {}) {
  const call = getOutermostCall(callNode);
  if (!call) return null;
  if (isAssertionValueCheckCall(call)) return null;

  const chain = extractCallChainFromCall(call);
  const terminal = chain.length ? chain[chain.length - 1] : "";
  if (!UI_TERMINAL_ACTIONS.has(terminal) && terminal !== "get" && terminal !== "contains") {
    return null;
  }

  const pageSymbolOrigins = ctx?.pageSymbolOrigins;
  const root = (chain[0] || "").split(".")[0];
  const locSub = findLocatorSubCall(call);
  let originKind = pageSymbolOrigins?.get(root) || null;
  if (!originKind && root) {
    originKind = inferPageWorkflowKind(chain[0] || root, pageSymbolOrigins);
  }

  if (originKind === "framework_page_instance" && locSub) {
    // Fall through to normal locator API classification below.
  } else if (originKind === "page_object_model" && !locSub) {
    return pageObjectMediatedLocator(chain, terminal);
  } else if (!locSub) {
    if (/Page$|Screen$|PO$/.test(root) && originKind !== "framework_page_instance") {
      return pageObjectMediatedLocator(chain, terminal);
    }
    return null;
  }

  const selectorArg = getFirstArg(locSub.call);
  const selectorLiteral = getFirstStringArg(locSub.call) || "";
  const selectorChannel = classifyApiLocatorArgKind(locSub.apiName, locSub.call, selectorLiteral);
  const strategy =
    strategyFromLocatorApi(locSub.apiName, selectorLiteral, locSub.call) || "unknown";
  let composition = hasPositionalRefinement(call)
    ? "positional_refinement"
    : hasChainedRefinement(call)
      ? "chained_refinement"
      : "direct_chain";
  if (originKind === "page_object_model") {
    composition = "page_object_mediated";
  }

  return {
    callee_chain: chain,
    terminal_action_ast: terminal,
    locator_api_ast: locSub.apiName,
    locator_strategy_ast: strategy,
    locator_composition_ast: composition,
    selector_literal_ast: selectorLiteral,
    selector_literal_kind_ast: selectorChannel,
    selector_channel_ast: selectorChannel,
    selector_value_origin_ast: selectorValueOrigin(selectorArg),
    has_positional_refinement_ast: hasPositionalRefinement(call),
    has_chained_refinement_ast: hasChainedRefinement(call),
    ast_confidence: strategy === "unknown" ? "low" : "high",
  };
}

function classifyWaitArg(firstArg) {
  if (!firstArg) return { wait_arg_kind_ast: "none", wait_subtype_ast: "unresolved_custom_wait" };
  if (Node.isStringLiteral(firstArg) || Node.isNoSubstitutionTemplateLiteral(firstArg)) {
    const literal = firstArg.getLiteralText?.() ?? "";
    if (literal.startsWith("@")) {
      return {
        wait_arg_kind_ast: "network_alias",
        wait_subtype_ast: "network_wait",
        wait_evidence_basis_ast: "ast_string_literal",
      };
    }
    return {
      wait_arg_kind_ast: "string_literal",
      wait_subtype_ast: "unresolved_custom_wait",
      wait_evidence_basis_ast: "ast_string_literal",
    };
  }
  if (Node.isTemplateExpression(firstArg)) {
    const head = firstArg.getHead?.().getLiteralText?.() ?? "";
    if (head.startsWith("@")) {
      return {
        wait_arg_kind_ast: "network_alias_expression",
        wait_subtype_ast: "network_wait",
        wait_evidence_basis_ast: "ast_template_literal_head",
      };
    }
    return {
      wait_arg_kind_ast: "template_expression",
      wait_subtype_ast: "unresolved_custom_wait",
      wait_evidence_basis_ast: "ast_template_expression",
    };
  }
  if (Node.isArrayLiteralExpression(firstArg)) {
    const elements = firstArg.getElements();
    const isAliasElement = (el) => {
      if (
        (Node.isStringLiteral(el) || Node.isNoSubstitutionTemplateLiteral(el)) &&
        (el.getLiteralText?.() ?? "").startsWith("@")
      ) {
        return true;
      }
      if (Node.isTemplateExpression(el) && (el.getHead?.().getLiteralText?.() ?? "").startsWith("@")) {
        return true;
      }
      if (Node.isSpreadElement?.(el)) {
        const spreadExpr = el.getExpression?.();
        return Boolean(spreadExpr && aliasyName(spreadExpr.getText()));
      }
      return false;
    };
    const aliasElements = elements.filter(
      (el) => isAliasElement(el)
    );
    if (elements.length > 0 && aliasElements.length === elements.length) {
      return {
        wait_arg_kind_ast: "network_alias_array",
        wait_subtype_ast: "network_wait",
        wait_evidence_basis_ast: "ast_array_literal",
      };
    }
    return {
      wait_arg_kind_ast: "array_expression",
      wait_subtype_ast: "unresolved_custom_wait",
      wait_evidence_basis_ast: "ast_array_literal",
    };
  }
  if (Node.isNumericLiteral(firstArg)) {
    return {
      wait_arg_kind_ast: "fixed_ms",
      wait_subtype_ast: "fixed_delay_literal",
      wait_evidence_basis_ast: "ast_numeric_literal",
    };
  }
  if (Node.isCallExpression(firstArg) && getCallName(firstArg) === "fill") {
    const expr = firstArg.getExpression();
    const receiver = Node.isPropertyAccessExpression(expr) ? expr.getExpression() : null;
    const fillArg = firstArg.getArguments()[0];
    const fillLiteral =
      fillArg && (Node.isStringLiteral(fillArg) || Node.isNoSubstitutionTemplateLiteral(fillArg))
        ? fillArg.getLiteralText?.() ?? ""
        : fillArg && Node.isTemplateExpression(fillArg)
          ? fillArg.getHead?.().getLiteralText?.() ?? ""
          : "";
    if (
      fillLiteral.startsWith("@") &&
      receiver &&
      (Node.isArrayLiteralExpression(receiver) ||
        (Node.isCallExpression(receiver) && getCallName(receiver) === "Array"))
    ) {
      return {
        wait_arg_kind_ast: "network_alias_array",
        wait_subtype_ast: "network_wait",
        wait_evidence_basis_ast: "ast_array_fill_alias",
      };
    }
  }
  if (Node.isIdentifier(firstArg) && aliasyName(firstArg.getText())) {
    return {
      wait_arg_kind_ast: "network_alias_expression",
      wait_subtype_ast: "network_wait",
      wait_evidence_basis_ast: "ast_symbol_name_heuristic",
    };
  }
  if (Node.isIdentifier(firstArg) && timeyName(firstArg.getText())) {
    return {
      wait_arg_kind_ast: "time_expression",
      wait_subtype_ast: "fixed_delay_expression",
      wait_evidence_basis_ast: "ast_symbol_name_heuristic",
    };
  }
  if (isTimeoutConstantNode(firstArg)) {
    return {
      wait_arg_kind_ast: "timeout_constant",
      wait_subtype_ast: "fixed_delay_expression",
      wait_evidence_basis_ast: "ast_symbol_name_heuristic",
    };
  }
  const timeExpr = classifyTimeExpressionNode(firstArg);
  if (timeExpr) {
    return {
      wait_arg_kind_ast: "time_expression",
      wait_subtype_ast: "fixed_delay_expression",
      wait_evidence_basis_ast: timeExpr.wait_evidence_basis_ast,
    };
  }
  return {
    wait_arg_kind_ast: "expression",
    wait_subtype_ast: "unresolved_custom_wait",
    wait_evidence_basis_ast: "ast_expression_unresolved",
  };
}

function firstArgIsFunction(call) {
  const first = call.getArguments()[0];
  return Boolean(first && (Node.isArrowFunction(first) || Node.isFunctionExpression(first)));
}

function callReceiverCall(call) {
  if (!call || !Node.isCallExpression(call)) return null;
  const expr = call.getExpression();
  if (!Node.isPropertyAccessExpression(expr)) return null;
  let receiver = expr.getExpression();
  while (receiver && Node.isPropertyAccessExpression(receiver)) {
    receiver = receiver.getExpression();
  }
  return Node.isCallExpression(receiver) ? receiver : null;
}

function callChainCalls(startCall) {
  const calls = [];
  let current = getOutermostCall(startCall) || startCall;
  for (let depth = 0; depth < 30; depth++) {
    if (!current || !Node.isCallExpression(current)) break;
    calls.push(current);
    current = callReceiverCall(current);
  }
  return calls;
}

function assertionRetryEvidenceFromCall(startCall) {
  for (const call of callChainCalls(startCall)) {
    const name = getCallName(call);
    const normalized = String(name || "").toLowerCase();
    if (RETRYABLE_ASSERT_MATCHERS.has(normalized)) {
      return {
        wait_subtype_ast: "assertion_retry_wait",
        wait_api_ast: "expect",
        wait_arg_kind_ast: "assertion_retry",
        wait_evidence_basis_ast: "ast_assertion_matcher",
        ast_confidence: "high",
      };
    }
    if (name === "should" || name === "and") {
      const semanticMatcher = getFirstStringArg(call);
      if (semanticMatcher) {
        return {
          wait_subtype_ast: "assertion_retry_wait",
          wait_api_ast: "cy.should",
          wait_arg_kind_ast: "assertion_retry",
          wait_evidence_basis_ast: "ast_assertion_call",
          ast_confidence: "high",
        };
      }
      if (firstArgIsFunction(call)) {
        return {
          wait_subtype_ast: "assertion_retry_wait",
          wait_api_ast: "cy.should",
          wait_arg_kind_ast: "assertion_retry",
          wait_evidence_basis_ast: "ast_assertion_callback",
          ast_confidence: "medium",
        };
      }
    }
  }
  return null;
}

function timeyName(name) {
  const lower = String(name || "").toLowerCase();
  return [
    "timeout",
    "delay",
    "wait",
    "msec",
    "millis",
    "milliseconds",
    "duration",
    "interval",
    "retry",
    "sleep",
    "pause",
    "throttle",
    "debounce",
  ].some((token) => lower.includes(token)) || lower === "ms" || lower.endsWith("ms") || lower.endsWith("sec");
}

function aliasyName(name) {
  const lower = String(name || "").toLowerCase();
  return lower.endsWith("aliases") ||
    lower.includes("aliases") ||
    lower.includes("aliasarray") ||
    lower.includes("aliaslist") ||
    lower.includes("waitalias") ||
    lower.includes("interceptalias") ||
    lower.includes("routewait");
}

function isTimeoutConstantNode(node) {
  if (!node) return false;
  if (Node.isIdentifier(node)) {
    const text = node.getText();
    return text === text.toUpperCase() && timeyName(text);
  }
  if (Node.isPropertyAccessExpression(node)) {
    const receiver = node.getExpression().getText();
    return receiver === receiver.toUpperCase() && timeyName(node.getName());
  }
  return false;
}

function classifyTimeExpressionNode(node) {
  if (!node) return false;
  if (Node.isParenthesizedExpression?.(node)) {
    return classifyTimeExpressionNode(node.getExpression());
  }
  if (Node.isBinaryExpression(node)) {
    const left = node.getLeft();
    const right = node.getRight();
    if (Node.isNumericLiteral(left) || Node.isNumericLiteral(right)) {
      return { wait_evidence_basis_ast: "ast_binary_numeric_expression" };
    }
    if (
      isTimeoutConstantNode(left) ||
      isTimeoutConstantNode(right) ||
      classifyTimeExpressionNode(left) ||
      classifyTimeExpressionNode(right)
    ) {
      return { wait_evidence_basis_ast: "ast_symbol_name_heuristic" };
    }
  }
  if (Node.isCallExpression(node)) {
    return timeyName(getCallName(node))
      ? { wait_evidence_basis_ast: "ast_symbol_name_heuristic" }
      : null;
  }
  if (Node.isPropertyAccessExpression(node)) {
    return timeyName(node.getName()) || timeyName(node.getExpression().getText())
      ? { wait_evidence_basis_ast: "ast_symbol_name_heuristic" }
      : null;
  }
  return isTimeoutConstantNode(node)
    ? { wait_evidence_basis_ast: "ast_symbol_name_heuristic" }
    : null;
}

function extractWaitInfo(callNode, framework) {
  const call = getOutermostCall(callNode);
  if (!call) return null;
  const api = getCallName(call);
  const recv = (() => {
    const ex = call.getExpression();
    if (Node.isPropertyAccessExpression(ex)) return ex.getExpression().getText();
    return "";
  })();

  if (api === "wait") {
    if (recv === "cy" || framework === "Cypress") {
      const arg = call.getArguments()[0];
      const argInfo = classifyWaitArg(arg);
      return {
        wait_api_ast: "cy.wait",
        ...argInfo,
        ast_confidence:
          argInfo.wait_subtype_ast === "network_wait"
            ? "high"
            : argInfo.wait_subtype_ast === "unresolved_custom_wait"
              ? "low"
              : "medium",
      };
    }
    if (recv === "t" || framework === "TestCafe") {
      return {
        wait_api_ast: "t.wait",
        wait_arg_kind_ast: "fixed_ms",
        wait_subtype_ast: "fixed_delay",
        wait_evidence_basis_ast: "ast_wait_api",
        ast_confidence: "high",
      };
    }
  }

  if (api === "waitForTimeout") {
    const arg = call.getArguments()[0];
    const argInfo = classifyWaitArg(arg);
    const subtype =
      argInfo.wait_subtype_ast === "fixed_delay_literal"
        ? "fixed_delay_literal"
        : "fixed_delay_expression";
    return {
      wait_api_ast: "page.waitForTimeout",
      ...argInfo,
      wait_subtype_ast: subtype,
      ast_confidence: subtype === "fixed_delay_literal" ? "high" : "medium",
    };
  }

  const navWaits = new Set(["waitForURL", "waitForNavigation", "waitForLoadState"]);
  const elemWaits = new Set([
    "waitForSelector", "waitForDisplayed", "waitForVisible", "waitForClickable",
    "waitForElementVisible", "waitFor",
  ]);
  const networkWaits = new Set([
    "waitForResponse", "waitForRequest", "waitForNetworkIdle",
  ]);

  if (navWaits.has(api)) {
    return {
      wait_api_ast: api,
      wait_arg_kind_ast: "condition",
      wait_subtype_ast: "navigation_or_load_wait",
      wait_evidence_basis_ast: "ast_wait_api",
      ast_confidence: "high",
    };
  }
  if (elemWaits.has(api)) {
    return {
      wait_api_ast: api,
      wait_arg_kind_ast: "condition",
      wait_subtype_ast: "element_state_wait",
      wait_evidence_basis_ast: "ast_wait_api",
      ast_confidence: "high",
    };
  }
  if (api === "waitUntil") {
    return {
      wait_api_ast: api,
      wait_arg_kind_ast: "predicate",
      wait_subtype_ast: "predicate_or_custom_condition",
      wait_evidence_basis_ast: "ast_wait_api",
      ast_confidence: "high",
    };
  }
  if (networkWaits.has(api)) {
    return {
      wait_api_ast: api,
      wait_arg_kind_ast: "network",
      wait_subtype_ast: "network_wait",
      wait_evidence_basis_ast: "ast_wait_api",
      ast_confidence: "high",
    };
  }
  if (api === "waitForEvent") {
    return {
      wait_api_ast: api,
      wait_arg_kind_ast: "event",
      wait_subtype_ast: "event_wait",
      wait_evidence_basis_ast: "ast_wait_api",
      ast_confidence: "high",
    };
  }
  if (api === "waitForFunction") {
    return {
      wait_api_ast: api,
      wait_arg_kind_ast: "predicate",
      wait_subtype_ast: "predicate_or_custom_condition",
      wait_evidence_basis_ast: "ast_wait_api",
      ast_confidence: "high",
    };
  }

  return null;
}

function extractAssertionSyncInfo(callNode) {
  const call = getOutermostCall(callNode);
  if (!call) return null;
  return assertionRetryEvidenceFromCall(call);
}

const FRAMEWORK_PAGE_NATIVE = new Set([
  "goto", "locator", "getbyrole", "getbytext", "getbylabel", "getbyplaceholder",
  "getbytestid", "getbyalttext", "getbytitle", "context", "newpage", "close",
  "waitforurl", "waitforloadstate", "waitforevent", "setcontent",
]);

function isFrameworkPageNativeMethod(method) {
  const m = (method || "").toLowerCase();
  return FRAMEWORK_PAGE_NATIVE.has(m) || m.startsWith("getby") || m.startsWith("findby");
}

function isPageLikeHelperFunction(name) {
  const root = (name || "").split(".")[0];
  if ((name || "").includes(".")) return false;
  return /^(waitFor|visit|moveTo|goTo|navigateTo|open)[A-Za-z0-9]*Page$/i.test(root);
}

function inferPageWorkflowKind(name, pageSymbolOrigins) {
  const root = (name || "").split(".")[0];
  if (isPageLikeHelperFunction(name)) return null;
  if (pageSymbolOrigins && pageSymbolOrigins.get(root)) {
    return pageSymbolOrigins.get(root);
  }
  if (!/^(?:[A-Z][A-Za-z0-9]*|[a-z][a-zA-Z0-9]*)(?:Page|Screen|PO|PageObject)$/.test(root)) {
    return null;
  }
  const parts = (name || "").split(".");
  if (/^[A-Z]/.test(root)) return "page_object_model";
  if (parts.length >= 3) return "page_object_model";
  const method = parts[1] || "";
  if (parts.length === 2 && isFrameworkPageNativeMethod(method)) {
    return "framework_page_instance";
  }
  if (parts.length === 2) return "page_object_model";
  return "page_object_model";
}

function isLikelyPageObjectInstance(root, fullName, pageSymbolOrigins) {
  if (!/^[a-z][a-zA-Z0-9]*(?:Page|Screen|PO|PageObject)$/.test(root || "")) return false;
  const kind = inferPageWorkflowKind(fullName || root, pageSymbolOrigins);
  return kind === "page_object_model";
}

function isPageObjectRoot(name, pageSymbolOrigins) {
  return inferPageWorkflowKind(name, pageSymbolOrigins) === "page_object_model";
}

const CYPRESS_BUILTIN_NON_WORKFLOW = new Set([
  "request",
  "intercept",
  "fixture",
  "task",
  "clock",
  "viewport",
  "screenshot",
  "log",
  "wrap",
  "then",
  "within",
]);

const CYPRESS_WORKFLOW_UI_ACTIONS = new Set([
  "click", "dblclick", "type", "realtype", "visit", "fill", "select", "check",
  "uncheck", "trigger", "mount", "clear", "press", "realclick", "realpress",
  "realhover", "hover", "tap", "getbyrole", "getbytext",
]);
const CYPRESS_DOMAIN_COMMAND_PREFIXES = [
  "uiSave", "uiAdd", "uiRemove", "uiDelete", "uiReset", "uiClear", "uiLoad",
  "uiPost", "uiOpen", "uiClose", "postMessage", "seed", "reset", "setup", "init",
];

function startsWithUppercaseSuffix(value, prefix) {
  if (!value.startsWith(prefix) || value.length <= prefix.length) return false;
  const ch = value.charCodeAt(prefix.length);
  return ch >= 65 && ch <= 90;
}

function commandNameSuggestsDomainHelper(cmd) {
  const name = String(cmd || "");
  if (!name) return false;
  if (CYPRESS_DOMAIN_COMMAND_PREFIXES.some((prefix) => name.startsWith(prefix))) return true;
  return startsWithUppercaseSuffix(name, "api");
}

function inferCyCustomWorkflowKindDetail(call, cmd) {
  const chain = extractCallChainFromCall(call);
  const names = chain[0] === "cy" ? chain.slice(1) : chain;
  const lowered = names.map((name) => String(name || "").toLowerCase());
  const hasUiAction = lowered.some((name) => CYPRESS_WORKFLOW_UI_ACTIONS.has(name));
  const hasWaitAfterCustom = lowered.includes("wait") && lowered.some((name) => {
    return name && name !== "wait" && !CYPRESS_BUILTIN_NON_WORKFLOW.has(name);
  });

  if (hasUiAction) {
    return {
      workflow_kind_ast: "cypress_custom_command",
      workflow_kind_basis_ast: "ast_cypress_ui_action_chain",
      ast_confidence: "medium",
    };
  }
  if (commandNameSuggestsDomainHelper(cmd)) {
    return {
      workflow_kind_ast: "domain_helper",
      workflow_kind_basis_ast: "ast_callee_name_heuristic",
      ast_confidence: "low",
    };
  }
  if (hasWaitAfterCustom) {
    return {
      workflow_kind_ast: "domain_helper",
      workflow_kind_basis_ast: "ast_cypress_wait_chain",
      ast_confidence: "medium",
    };
  }
  return {
    workflow_kind_ast: "cypress_custom_command",
    workflow_kind_basis_ast: "ast_cypress_custom_command_call",
    ast_confidence: "medium",
  };
}

function extractFixtureProvenance(call, fixtureProvenanceMap) {
  if (!fixtureProvenanceMap || fixtureProvenanceMap.size === 0) return null;
  const expr = call.getExpression().getText();
  const root = expr.split(".")[0];
  const prov = fixtureProvenanceMap.get(root);
  if (!prov) return null;
    return {
      workflow_kind_ast: "playwright_fixture",
      workflow_kind_basis_ast: "ast_playwright_fixture_param",
      fixture_param_name: root,
      fixture_declared_by: prov.declaredBy || "test_callback",
      fixture_scope: prov.scope || "test",
    fixture_usage_kind: "callback_parameter",
    callee_object_ast: root,
    ast_confidence: "high",
  };
}

function extractWorkflowInfo(callNode, importMap, ctx) {
  const call = getOutermostCall(callNode);
  if (!call) return null;
  const fixtureProv = extractFixtureProvenance(call, ctx?.fixtureProvenanceMap);
  if (fixtureProv) return fixtureProv;

  const pageSymbolOrigins = ctx?.pageSymbolOrigins;
  const expr = call.getExpression().getText();
  const root = expr.split(".")[0];
  const pageKind = inferPageWorkflowKind(expr, pageSymbolOrigins);
  if (pageKind) {
    return {
      workflow_kind_ast: pageKind,
      workflow_kind_basis_ast: pageSymbolOrigins?.get(root)
        ? "ast_page_symbol_origin"
        : "ast_page_object_name_heuristic",
      page_symbol_origin_ast: pageSymbolOrigins?.get(root) || pageKind,
      callee_object_ast: root,
      ast_confidence: pageSymbolOrigins?.get(root) ? "high" : "medium",
    };
  }
  if (expr.startsWith("cy.") && root === "cy") {
    const cmd = getCallName(call);
    if (cmd && CYPRESS_BUILTIN_NON_WORKFLOW.has(cmd)) {
      return null;
    }
    if (cmd && cmd !== "get" && cmd !== "visit") {
      const detail = inferCyCustomWorkflowKindDetail(call, cmd);
      return { ...detail, callee_object_ast: "cy" };
    }
  }
  if (isLikelyHelperRoot(root, importMap)) {
    return {
      workflow_kind_ast: "domain_helper",
      workflow_kind_basis_ast: importMap?.has(root)
        ? "ast_local_imported_helper"
        : "ast_helper_name_heuristic",
      callee_object_ast: root,
      ast_confidence: "medium",
    };
  }
  return null;
}

function isLikelyHelperRoot(root, importMap) {
  if (!root || /^[a-z]/.test(root) === false && !/^[A-Z]/.test(root)) return false;
  if (isPageObjectRoot(root)) return false;
  if (/^(page|cy|browser|t|expect|test|describe|it)$/.test(root)) return false;
  if (/^[A-Z]/.test(root) && /(Helper|Utils?|Steps|Actions|Flow)$/.test(root)) return true;
  if (importMap && importMap.has(root)) {
    const entry = importMap.get(root);
    const spec = entry && typeof entry === "object" ? entry.spec : entry;
    if (spec && (spec.startsWith(".") || spec.startsWith("~/") || spec.startsWith("@/"))) return true;
  }
  return /^[a-z][a-zA-Z0-9]{2,}(User|Admin|Login|Setup)$/.test(root);
}

function attachAstPatternFields(node, featureType, framework, importMap, ctx) {
  const out = {};
  const call = Node.isCallExpression(node) ? node : getOutermostCall(node);
  if (!call) return out;

  if (featureType === "ui_action") {
    const loc = extractLocatorInfo(call, framework, ctx);
    if (loc) {
      out.callee_chain_json = JSON.stringify(loc.callee_chain || []);
      out.terminal_action_ast = loc.terminal_action_ast || "";
      out.locator_api_ast = loc.locator_api_ast || "";
      out.locator_strategy_ast = loc.locator_strategy_ast || "";
      out.locator_composition_ast = loc.locator_composition_ast || "";
      out.selector_literal_ast = (loc.selector_literal_ast || "").slice(0, 200);
      out.selector_literal_kind_ast = loc.selector_literal_kind_ast || "";
      out.selector_channel_ast = loc.selector_channel_ast || "";
      out.selector_value_origin_ast = loc.selector_value_origin_ast || "";
      out.has_positional_refinement_ast = Boolean(loc.has_positional_refinement_ast);
      out.has_chained_refinement_ast = Boolean(loc.has_chained_refinement_ast);
      out.ast_confidence = loc.ast_confidence || "";
    }
  }

  if (featureType === "wait_synchronization") {
    const w = extractWaitInfo(call, framework);
    if (w) {
      out.wait_api_ast = w.wait_api_ast || "";
      out.wait_arg_kind_ast = w.wait_arg_kind_ast || "";
      out.wait_subtype_ast = w.wait_subtype_ast || "";
      out.wait_evidence_basis_ast = w.wait_evidence_basis_ast || "";
      out.ast_confidence = w.ast_confidence || "";
    }
  }

  if (featureType === "assertion") {
    const a = extractAssertionSyncInfo(call);
    if (a) {
      out.wait_subtype_ast = a.wait_subtype_ast;
      out.wait_api_ast = a.wait_api_ast;
      out.wait_arg_kind_ast = a.wait_arg_kind_ast;
      out.wait_evidence_basis_ast = a.wait_evidence_basis_ast;
      out.ast_confidence = a.ast_confidence;
    }
  }

  if (featureType === "helper_call" || featureType === "ui_action") {
    const wf = extractWorkflowInfo(call, importMap, ctx);
    if (wf) {
      out.workflow_kind_ast = wf.workflow_kind_ast || "";
      out.workflow_kind_basis_ast = wf.workflow_kind_basis_ast || "";
      out.callee_object_ast = wf.callee_object_ast || "";
      out.ast_confidence = wf.ast_confidence || "";
      if (wf.fixture_param_name) {
        out.fixture_param_name = wf.fixture_param_name;
        out.fixture_declared_by = wf.fixture_declared_by || "";
        out.fixture_scope = wf.fixture_scope || "";
        out.fixture_usage_kind = wf.fixture_usage_kind || "";
      }
      if (wf.page_symbol_origin_ast) {
        out.page_symbol_origin_ast = wf.page_symbol_origin_ast;
      }
    }
  }

  return out;
}

module.exports = {
  attachAstPatternFields,
  extractLocatorInfo,
  extractWaitInfo,
  extractAssertionSyncInfo,
  extractWorkflowInfo,
  extractCallChainFromCall,
  findLocatorSubCall,
  getCallName,
  getOutermostCall,
  classifySelectorLiteralKind,
  selectorChannelFromAttributeLiteral,
  strategyFromSelectorChannel,
};
