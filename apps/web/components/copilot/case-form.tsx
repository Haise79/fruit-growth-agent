"use client";

import { useState } from "react";

import type { CopilotCaseCreate } from "@/lib/types";

type CaseFormProps = {
  isSubmitting: boolean;
  requestFailed: boolean;
  onSubmit: (request: CopilotCaseCreate) => Promise<void>;
};

const EMPTY_SKUS = ["", "", ""];

export function CaseForm({
  isSubmitting,
  requestFailed,
  onSubmit,
}: CaseFormProps) {
  const [message, setMessage] = useState("");
  const [skuCodes, setSkuCodes] = useState(EMPTY_SKUS);
  const [validationError, setValidationError] = useState("");

  async function submit() {
    const normalizedMessage = message.trim();
    if (normalizedMessage.length < 1 || normalizedMessage.length > 4000) {
      setValidationError("客户消息必须为 1–4000 个字符");
      return;
    }
    setValidationError("");
    await onSubmit({
      message: normalizedMessage,
      selected_sku_codes: skuCodes
        .map((code) => code.trim())
        .filter(Boolean),
    });
  }

  return (
    <section className="copilot-compose" aria-labelledby="copilot-compose-title">
      <div className="section-heading">
        <div>
          <h2 id="copilot-compose-title">生成客服建议</h2>
          <p>粘贴消息，系统仅生成可编辑建议，不会向客户发送。</p>
        </div>
        <span className="character-count">{message.length} / 4000</span>
      </div>
      <label className="field-label" htmlFor="customer-message">
        客户消息
      </label>
      <textarea
        className="message-input"
        id="customer-message"
        maxLength={4000}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="粘贴客户原始消息"
        required
        rows={5}
        value={message}
      />
      <fieldset className="sku-fields">
        <legend>可选 SKU（最多 3 个）</legend>
        {skuCodes.map((code, index) => (
          <label key={index}>
            <span>SKU 代码 {index + 1}</span>
            <input
              onChange={(event) =>
                setSkuCodes((current) =>
                  current.map((value, currentIndex) =>
                    currentIndex === index ? event.target.value : value,
                  ),
                )
              }
              value={code}
            />
          </label>
        ))}
      </fieldset>
      {validationError ? (
        <p className="form-error" role="alert">
          {validationError}
        </p>
      ) : null}
      <button
        className="primary-button copilot-submit"
        disabled={isSubmitting}
        onClick={submit}
        type="button"
      >
        {isSubmitting ? "正在生成…" : requestFailed ? "重新生成" : "生成建议"}
      </button>
    </section>
  );
}
