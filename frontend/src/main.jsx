import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";

import {
  ArrowDownLeft,
  ArrowUpRight,
  RefreshCw,
  Send,
  WalletCards,
  LogOut,
  Activity,
  ShieldCheck,
  Search,
  CheckCircle2,
  ArrowLeft,
} from "lucide-react";

import "./styles.css";

/* =========================================================
   API
========================================================= */

const API =
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API,
  timeout: 15000,
});

/* =========================================================
   AUTH INTERCEPTOR
========================================================= */

api.interceptors.request.use(
  (config) => {
    const token =
      localStorage.getItem("access_token");

    if (token) {
      config.headers.Authorization =
        `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

/* =========================================================
   HELPERS
========================================================= */

function money(amount) {
  const value = Number(amount ?? 0);

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value / 100);
}

/*
 * Normalize transaction data coming from the API.
 *
 * Expected backend transaction:
 *
 * {
 *   id,
 *   transaction_type,
 *   amount,
 *   entry_type,
 *   direction,
 *   counterparty_name,
 *   counterparty_email,
 *   ...
 * }
 */

function normalizeTransaction(transaction) {
  const amount =
    transaction?.amount ??
    transaction?.entry_amount ??
    transaction?.value ??
    0;

  let entryType =
    transaction?.entry_type ??
    transaction?.direction ??
    null;

  if (typeof entryType === "string") {
    entryType = entryType.toUpperCase();
  }

  return {
    ...transaction,
    amount: Number(amount),
    entry_type: entryType,
  };
}

/* =========================================================
   ERROR HANDLING
========================================================= */

function getErrorMessage(error) {
  const detail =
    error?.response?.data?.detail;

  if (Array.isArray(detail)) {
    return detail
      .map(
        (item) =>
          item?.msg ||
          "Invalid request."
      )
      .join(", ");
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (
    error?.response?.data?.message
  ) {
    return error.response.data.message;
  }

  if (
    error?.response?.status === 401
  ) {
    return "Your session has expired. Please sign in again.";
  }

  if (
    error?.response?.status === 404
  ) {
    return "The requested resource was not found.";
  }

  if (
    error?.response?.status === 409
  ) {
    return "This request conflicts with an existing transaction.";
  }

  if (
    error?.response?.status === 422
  ) {
    return "Please check the information you entered.";
  }

  if (
    error?.message === "Network Error"
  ) {
    return "Unable to connect to PayFlow API. Make sure the backend is running on port 8000.";
  }

  return (
    error?.message ||
    "Something went wrong."
  );
}

/* =========================================================
   IDEMPOTENCY KEY
========================================================= */

function createIdempotencyKey() {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }

  return `payflow-${Date.now()}-${Math.random()
    .toString(36)
    .substring(2)}`;
}

/* =========================================================
   APP
========================================================= */

function App() {
  const [user, setUser] =
    useState(null);

  const [wallet, setWallet] =
    useState(null);

  const [tx, setTx] =
    useState([]);

  const [view, setView] =
    useState("dashboard");

  const [auth, setAuth] =
    useState("login");

  const [loading, setLoading] =
    useState(false);

  const [notice, setNotice] =
    useState("");

  const [noticeType, setNoticeType] =
    useState("success");

  /* =======================================================
     LOAD DASHBOARD
  ======================================================= */

  const load = async () => {
    try {
      const [
        userResponse,
        walletResponse,
        transactionResponse,
      ] = await Promise.all([
        api.get("/auth/me"),
        api.get("/wallet/me"),
        api.get("/transactions?limit=20"),
      ]);

      setUser(
        userResponse.data
      );

      setWallet(
        walletResponse.data
      );

      const rawTransactions =
        Array.isArray(
          transactionResponse.data
        )
          ? transactionResponse.data
          : [];

      const normalizedTransactions =
        rawTransactions.map(
          normalizeTransaction
        );

      console.log(
        "PAYFLOW TRANSACTIONS:",
        normalizedTransactions
      );

      setTx(
        normalizedTransactions
      );
    } catch (error) {
      console.error(
        "LOAD ERROR:",
        error?.response?.data ||
          error
      );

      if (
        error?.response?.status === 401
      ) {
        localStorage.removeItem(
          "access_token"
        );

        setUser(null);
        setWallet(null);
        setTx([]);
      }
    }
  };

  /* =======================================================
     INITIAL LOAD
  ======================================================= */

  useEffect(() => {
    const token =
      localStorage.getItem(
        "access_token"
      );

    if (token) {
      load();
    }
  }, []);

  /* =======================================================
     LOGOUT
  ======================================================= */

  const logout = () => {
    localStorage.removeItem(
      "access_token"
    );

    setUser(null);
    setWallet(null);
    setTx([]);
    setView("dashboard");
    setNotice("");
  };

  /* =======================================================
     TRANSACTION ACTION
  ======================================================= */

  const action = async (
    type,
    body
  ) => {
    setLoading(true);
    setNotice("");
    setNoticeType("success");

    try {
      console.log(
        "PAYFLOW TRANSACTION REQUEST:",
        {
          type,
          body,
        }
      );

      const response =
        await api.post(
          `/transactions/${type}`,
          body,
          {
            headers: {
              "Idempotency-Key":
                createIdempotencyKey(),

              "Content-Type":
                "application/json",
            },
          }
        );

      console.log(
        "PAYFLOW TRANSACTION RESPONSE:",
        response.data
      );

      /*
       * Reload wallet and transactions
       * immediately after successful operation.
       */
      await load();

      if (type === "deposit") {
        setNotice(
          "Money added successfully."
        );
      } else if (
        type === "withdraw"
      ) {
        setNotice(
          "Withdrawal completed successfully."
        );
      } else if (
        type === "transfer"
      ) {
        setNotice(
          "Transfer completed successfully."
        );
      }

      setNoticeType("success");

      /*
       * Immediately return to dashboard.
       * No artificial timeout is required.
       */
      setView("dashboard");

      return true;
    } catch (error) {
      console.error(
        "PAYFLOW TRANSACTION ERROR:",
        error?.response?.data ||
          error
      );

      setNotice(
        getErrorMessage(error)
      );

      setNoticeType("error");

      return false;
    } finally {
      setLoading(false);
    }
  };

  /* =======================================================
     AUTH SCREEN
  ======================================================= */

  if (!user) {
    return (
      <Auth
        mode={auth}
        setMode={setAuth}
        onLogin={async (token) => {
          localStorage.setItem(
            "access_token",
            token
          );

          await load();
        }}
      />
    );
  }

  /* =======================================================
     MAIN APP
  ======================================================= */

  return (
    <div className="app">

      {/* ===================================================
          SIDEBAR
      =================================================== */}

      <aside>

        <div className="brand">

          <div className="logo">
            P
          </div>

          <span>
            PayFlow
          </span>

        </div>

        <nav>

          <button
            type="button"
            onClick={() =>
              setView("dashboard")
            }
            className={
              view === "dashboard"
                ? "active"
                : ""
            }
          >
            <Activity />
            Overview
          </button>

          <button
            type="button"
            onClick={() =>
              setView("deposit")
            }
            className={
              view === "deposit"
                ? "active"
                : ""
            }
          >
            <ArrowDownLeft />
            Deposit
          </button>

          <button
            type="button"
            onClick={() =>
              setView("withdraw")
            }
            className={
              view === "withdraw"
                ? "active"
                : ""
            }
          >
            <ArrowUpRight />
            Withdraw
          </button>

          <button
            type="button"
            onClick={() =>
              setView("transfer")
            }
            className={
              view === "transfer"
                ? "active"
                : ""
            }
          >
            <Send />
            Transfer
          </button>

        </nav>

        <button
          type="button"
          className="logout"
          onClick={logout}
        >
          <LogOut />
          Sign out
        </button>

      </aside>

      {/* ===================================================
          MAIN
      =================================================== */}

      <main>

        <header>

          <div>

            <p className="eyebrow">
              PERSONAL WALLET
            </p>

            <h1>
              Good to see you,{" "}
              {user.first_name}.
            </h1>

          </div>

          <div className="status">
            <span />
            Live
          </div>

        </header>

        {/* =================================================
            NOTICE
        ================================================= */}

        {notice && (
          <div
            className={
              noticeType === "error"
                ? "notice error-notice"
                : "notice"
            }
          >
            {notice}
          </div>
        )}

        {/* =================================================
            DASHBOARD
        ================================================= */}

        {view === "dashboard" && (
          <Dashboard
            wallet={wallet}
            tx={tx}
            refresh={load}
          />
        )}

        {/* =================================================
            TRANSACTION FORM
        ================================================= */}

        {view !== "dashboard" && (
          <TransactionForm
            type={view}
            loading={loading}
            onSubmit={action}
            wallet={wallet}
          />
        )}

      </main>

    </div>
  );
}

/* =========================================================
   AUTH
========================================================= */

function Auth({
  mode,
  setMode,
  onLogin,
}) {
  const [form, setForm] =
    useState({
      email: "",
      password: "",
      first_name: "",
      last_name: "",
    });

  const [err, setErr] =
    useState("");

  const submit = async (
    event
  ) => {
    event.preventDefault();

    setErr("");

    try {
      if (mode === "login") {

        const response =
          await api.post(
            "/auth/login",
            {
              email: form.email,
              password:
                form.password,
            }
          );

        await onLogin(
          response.data.access_token
        );

      } else {

        await api.post(
          "/auth/register",
          {
            email: form.email,
            password:
              form.password,
            first_name:
              form.first_name,
            last_name:
              form.last_name,
          }
        );

        const response =
          await api.post(
            "/auth/login",
            {
              email: form.email,
              password:
                form.password,
            }
          );

        await onLogin(
          response.data.access_token
        );
      }

    } catch (error) {

      console.error(
        "AUTH ERROR:",
        error?.response?.data ||
          error
      );

      setErr(
        getErrorMessage(error)
      );
    }
  };

  return (
    <div className="auth">

      <div className="auth-card">

        <div className="brand center">

          <div className="logo">
            P
          </div>

          <span>
            PayFlow
          </span>

        </div>

        <h1>
          {mode === "login"
            ? "Welcome back"
            : "Create your wallet"}
        </h1>

        <p className="muted">
          A secure digital wallet
          and payment platform built
          with FastAPI and PostgreSQL.
        </p>

        {err && (
          <div className="error">
            {err}
          </div>
        )}

        <form
          onSubmit={submit}
        >

          {mode === "register" && (
            <>

              <input
                placeholder="First name"
                required
                value={
                  form.first_name
                }
                onChange={(event) =>
                  setForm({
                    ...form,
                    first_name:
                      event.target.value,
                  })
                }
              />

              <input
                placeholder="Last name"
                required
                value={
                  form.last_name
                }
                onChange={(event) =>
                  setForm({
                    ...form,
                    last_name:
                      event.target.value,
                  })
                }
              />

            </>
          )}

          <input
            type="email"
            placeholder="Email"
            required
            value={form.email}
            onChange={(event) =>
              setForm({
                ...form,
                email:
                  event.target.value,
              })
            }
          />

          <input
            type="password"
            placeholder="Password"
            required
            value={form.password}
            onChange={(event) =>
              setForm({
                ...form,
                password:
                  event.target.value,
              })
            }
          />

          <button
            type="submit"
            className="primary"
          >
            {mode === "login"
              ? "Sign in"
              : "Create account"}
          </button>

        </form>

        <button
          type="button"
          className="link"
          onClick={() =>
            setMode(
              mode === "login"
                ? "register"
                : "login"
            )
          }
        >
          {mode === "login"
            ? "New to PayFlow? Create account"
            : "Already have an account? Sign in"}
        </button>

      </div>

    </div>
  );
}

/* =========================================================
   DASHBOARD
========================================================= */

function Dashboard({
  wallet,
  tx,
  refresh,
}) {
  return (
    <>

      {/* =================================================
          BALANCE
      ================================================= */}

      <section className="hero">

        <div>

          <p className="eyebrow">
            AVAILABLE BALANCE
          </p>

          <div className="balance">
            {money(
              wallet?.available_balance
            )}
          </div>

          <p className="muted">
            {wallet?.currency ||
              "INR"}
            {" · "}
            Active wallet
          </p>

        </div>

        <div className="wallet-icon">

          <WalletCards
            size={34}
          />

        </div>

      </section>

      <div className="grid">

        {/* =================================================
            RECENT ACTIVITY
        ================================================= */}

        <div className="panel">

          <div className="panel-head">

            <h2>
              Recent activity
            </h2>

            <button
              type="button"
              className="icon-btn"
              onClick={refresh}
              title="Refresh transactions"
            >
              <RefreshCw
                size={17}
              />
            </button>

          </div>

          {tx.length === 0 ? (

            <div className="empty">
              No transactions yet.
            </div>

          ) : (

            <div className="transaction-list">

              {tx.map(
                (transaction) => {

                  const type =
                    String(
                      transaction?.transaction_type ||
                      "TRANSACTION"
                    ).toUpperCase();

                  /* -----------------------------------------
                     AMOUNT
                  ----------------------------------------- */

                  const amount =
                    Number(
                      transaction?.amount ??
                      transaction?.entry_amount ??
                      transaction?.value ??
                      0
                    );

                  /* -----------------------------------------
                     ENTRY TYPE
                  ----------------------------------------- */

                  const entryType =
                    String(
                      transaction?.entry_type ??
                      transaction?.direction ??
                      ""
                    ).toUpperCase();

                  /* -----------------------------------------
                     CREDIT / DEBIT
                  ----------------------------------------- */

                  let isCredit = false;
                  let isDebit = false;

                  if (
                    type === "DEPOSIT"
                  ) {
                    isCredit = true;
                  }

                  if (
                    type === "WITHDRAWAL"
                  ) {
                    isDebit = true;
                  }

                  if (
                    type === "TRANSFER"
                  ) {

                    if (
                      entryType ===
                      "CREDIT"
                    ) {
                      isCredit = true;
                    }

                    if (
                      entryType ===
                      "DEBIT"
                    ) {
                      isDebit = true;
                    }

                  }

                  /*
                   * If the backend sends a
                   * direction field instead
                   * of entry_type, use it.
                   */

                  if (
                    !isCredit &&
                    !isDebit &&
                    entryType === "CREDIT"
                  ) {
                    isCredit = true;
                  }

                  if (
                    !isCredit &&
                    !isDebit &&
                    entryType === "DEBIT"
                  ) {
                    isDebit = true;
                  }

                  /*
                   * Safe fallback for unknown
                   * transaction direction.
                   */

                  if (
                    !isCredit &&
                    !isDebit
                  ) {
                    isDebit =
                      type ===
                      "WITHDRAWAL";
                  }

                  /* -----------------------------------------
                     COUNTERPARTY
                  ----------------------------------------- */

                  const counterpartyName =
                    transaction?.counterparty_name ||
                    transaction?.recipient_name ||
                    transaction?.sender_name ||
                    null;

                  const counterpartyEmail =
                    transaction?.counterparty_email ||
                    transaction?.recipient_email ||
                    transaction?.sender_email ||
                    null;

                  /* -----------------------------------------
                     DESCRIPTION
                  ----------------------------------------- */

                  const description =
                    transaction?.description ||
                    "Wallet transaction";

                  return (
                    <div
                      className={`tx ${
                        isCredit
                          ? "tx-credit"
                          : "tx-debit"
                      }`}
                      key={
                        transaction.id
                      }
                    >

                      {/* -----------------------------------
                          ICON
                      ----------------------------------- */}

                      <div className="tx-icon">

                        {isCredit ? (
                          <ArrowDownLeft />
                        ) : (
                          <ArrowUpRight />
                        )}

                      </div>

                      {/* -----------------------------------
                          DETAILS
                      ----------------------------------- */}

                      <div className="tx-main">

                        <b>
                          {type}
                        </b>

                        {type ===
                          "TRANSFER" &&
                        counterpartyName ? (

                          <>
                            <span>
                              {isCredit
                                ? `From ${counterpartyName}`
                                : `To ${counterpartyName}`}
                            </span>

                            {counterpartyEmail && (
                              <small>
                                {
                                  counterpartyEmail
                                }
                              </small>
                            )}
                          </>

                        ) : (

                          <span>
                            {description}
                          </span>

                        )}

                      </div>

                      {/* -----------------------------------
                          AMOUNT
                      ----------------------------------- */}

                      <strong
                        className={
                          isCredit
                            ? "amount-credit"
                            : "amount-debit"
                        }
                      >
                        {isDebit
                          ? "−"
                          : "+"}

                        {money(amount)}
                      </strong>

                    </div>
                  );
                }
              )}

            </div>
          )}

        </div>

        {/* =================================================
            FINANCIAL INTEGRITY
        ================================================= */}

        <div className="panel security">

          <ShieldCheck
            size={28}
          />

          <h2>
            Financial integrity
          </h2>

          <p>
            Every movement is recorded
            as a double-entry ledger
            transaction with idempotency
            protection and database row
            locking.
          </p>

          <div className="chips">

            <span>
              PostgreSQL
            </span>

            <span>
              JWT
            </span>

            <span>
              Idempotency
            </span>

            <span>
              ACID
            </span>

          </div>

        </div>

      </div>
    </>
  );
}

/* =========================================================
   TRANSACTION FORM
========================================================= */

function TransactionForm({
  type,
  onSubmit,
  loading,
  wallet,
}) {
  const [amount, setAmount] =
    useState("");

  const [desc, setDesc] =
    useState("");

  const [recipientQuery, setRecipientQuery] =
    useState("");

  const [recipients, setRecipients] =
    useState([]);

  const [selectedRecipient, setSelectedRecipient] =
    useState(null);

  const [searching, setSearching] =
    useState(false);

  const [step, setStep] =
    useState("form");

  const labels = {
    deposit: [
      "Add money",
      "Fund your wallet securely.",
    ],

    withdraw: [
      "Withdraw money",
      "Move funds out of your wallet.",
    ],

    transfer: [
      "Send money",
      "Transfer funds securely to another PayFlow user.",
    ],
  };

  /* =======================================================
     RESET WHEN TRANSACTION TYPE CHANGES
  ======================================================= */

  useEffect(() => {
    setAmount("");
    setDesc("");
    setRecipientQuery("");
    setRecipients([]);
    setSelectedRecipient(null);
    setStep("form");
  }, [type]);

  /* =======================================================
     RECIPIENT SEARCH
  ======================================================= */

  useEffect(() => {
    if (
      type !== "transfer"
    ) {
      return;
    }

    const query =
      recipientQuery.trim();

    if (
      query.length < 3
    ) {
      setRecipients([]);
      return;
    }

    const timer =
      setTimeout(
        async () => {
          try {

            setSearching(true);

            const response =
              await api.get(
                "/recipients/search",
                {
                  params: {
                    q: query,
                  },
                }
              );

            const items =
              Array.isArray(
                response.data
              )
                ? response.data
                : response.data?.items;

            setRecipients(
              Array.isArray(items)
                ? items
                : []
            );

          } catch (error) {

            console.error(
              "RECIPIENT SEARCH ERROR:",
              error?.response?.data ||
                error
            );

            setRecipients([]);

          } finally {

            setSearching(false);

          }
        },
        300
      );

    return () =>
      clearTimeout(timer);

  }, [
    recipientQuery,
    type,
  ]);

  /* =======================================================
     SELECT RECIPIENT
  ======================================================= */

  const selectRecipient = (
    recipient
  ) => {

    setSelectedRecipient(
      recipient
    );

    setRecipientQuery("");
    setRecipients([]);
  };

  /* =======================================================
     NORMAL FORM SUBMIT
  ======================================================= */

  const submit = (
    event
  ) => {

    event.preventDefault();

    const numericAmount =
      Number(amount);

    if (
      !numericAmount ||
      numericAmount <= 0
    ) {
      alert(
        "Please enter a valid amount."
      );

      return;
    }

    const amountInPaise =
      Math.round(
        numericAmount * 100
      );

    /* -----------------------------------------
       BALANCE CHECK
    ----------------------------------------- */

    if (
      wallet &&
      type !== "deposit" &&
      amountInPaise >
        Number(
          wallet.available_balance ||
            0
        )
    ) {

      alert(
        `Insufficient balance. Available balance: ${money(
          wallet.available_balance
        )}`
      );

      return;
    }

    /* -----------------------------------------
       TRANSFER RECIPIENT CHECK
    ----------------------------------------- */

    if (
      type === "transfer" &&
      !selectedRecipient
    ) {

      alert(
        "Please select a recipient."
      );

      return;
    }

    /* -----------------------------------------
       TRANSFER REVIEW
    ----------------------------------------- */

    if (
      type === "transfer"
    ) {

      setStep("review");

      return;
    }

    /* -----------------------------------------
       DEPOSIT / WITHDRAW
    ----------------------------------------- */

    const body = {
      amount:
        amountInPaise,

      description:
        desc.trim() ||
        undefined,
    };

    onSubmit(
      type,
      body
    );
  };

  /* =======================================================
     CONFIRM TRANSFER
  ======================================================= */

  const confirm = async () => {

    if (loading) {
      return;
    }

    if (!selectedRecipient) {

      alert(
        "Please select a recipient."
      );

      setStep("form");

      return;
    }

    const numericAmount =
      Number(amount);

    if (
      !numericAmount ||
      numericAmount <= 0
    ) {

      alert(
        "Please enter a valid amount."
      );

      setStep("form");

      return;
    }

    const amountInPaise =
      Math.round(
        numericAmount * 100
      );

    /* -----------------------------------------
       BALANCE CHECK
    ----------------------------------------- */

    if (
      wallet &&
      amountInPaise >
        Number(
          wallet.available_balance ||
            0
        )
    ) {

      alert(
        `Insufficient balance. Available balance: ${money(
          wallet.available_balance
        )}`
      );

      setStep("form");

      return;
    }

    /* -----------------------------------------
       RECIPIENT WALLET
    ----------------------------------------- */

    const recipientWalletId =
      selectedRecipient?.wallet_id;

    if (!recipientWalletId) {

      console.error(
        "Recipient object:",
        selectedRecipient
      );

      alert(
        "Recipient wallet information is missing. Check /recipients/search response."
      );

      return;
    }

    /* -----------------------------------------
       TRANSFER BODY
    ----------------------------------------- */

    const body = {
      amount:
        amountInPaise,

      recipient_wallet_id:
        recipientWalletId,

      description:
        desc.trim() ||
        undefined,
    };

    console.log(
      "TRANSFER REQUEST:",
      body
    );

    /* -----------------------------------------
       CALL BACKEND
    ----------------------------------------- */

    const success =
      await onSubmit(
        "transfer",
        body
      );

    if (!success) {
      return;
    }

    /*
     * App.action() already:
     *
     * 1. Calls backend
     * 2. Commits transaction
     * 3. Reloads wallet
     * 4. Reloads transactions
     * 5. Returns to dashboard
     */

  };

  /* =======================================================
     TRANSFER REVIEW SCREEN
  ======================================================= */

  if (
    type === "transfer" &&
    step === "review"
  ) {

    const transferAmount =
      Math.round(
        Number(amount) * 100
      );

    return (
      <div className="form-wrap">

        <div className="panel form-panel">

          {/* ---------------------------------------------
              BACK
          --------------------------------------------- */}

          <button
            type="button"
            className="back-button"
            onClick={() =>
              setStep("form")
            }
            disabled={loading}
          >
            <ArrowLeft
              size={17}
            />

            Back
          </button>

          {/* ---------------------------------------------
              TITLE
          --------------------------------------------- */}

          <p className="eyebrow">
            REVIEW TRANSFER
          </p>

          <h2>
            Confirm your transfer
          </h2>

          {/* ---------------------------------------------
              RECIPIENT
          --------------------------------------------- */}

          <div className="review-card">

            <span className="muted">
              Sending to
            </span>

            <strong>
              {
                selectedRecipient?.first_name
              }{" "}
              {
                selectedRecipient?.last_name
              }
            </strong>

            <span>
              {
                selectedRecipient?.email
              }
            </span>

          </div>

          {/* ---------------------------------------------
              AMOUNT
          --------------------------------------------- */}

          <div className="review-amount">
            {money(
              transferAmount
            )}
          </div>

          {desc && (
            <p className="muted">
              Note: {desc}
            </p>
          )}

          {/* ---------------------------------------------
              TRANSFER AMOUNT
          --------------------------------------------- */}

          <div className="review-row">

            <span>
              Transfer amount
            </span>

            <strong>
              {money(
                transferAmount
              )}
            </strong>

          </div>

          {/* ---------------------------------------------
              FEE
          --------------------------------------------- */}

          <div className="review-row">

            <span>
              Fee
            </span>

            <strong>
              ₹0.00
            </strong>

          </div>

          {/* ---------------------------------------------
              TOTAL
          --------------------------------------------- */}

          <div className="review-row total">

            <span>
              Total
            </span>

            <strong>
              {money(
                transferAmount
              )}
            </strong>

          </div>

          {/* ---------------------------------------------
              CONFIRM BUTTON
          --------------------------------------------- */}

          <button
            type="button"
            className="primary"
            onClick={confirm}
            disabled={
              loading ||
              !selectedRecipient
            }
          >
            {loading
              ? "Processing..."
              : "Confirm transfer"}
          </button>

        </div>

      </div>
    );
  }

  /* =======================================================
     NORMAL FORM
  ======================================================= */

  return (
    <div className="form-wrap">

      <div className="panel form-panel">

        <p className="eyebrow">
          TRANSACTION
        </p>

        <h2>
          {labels[type][0]}
        </h2>

        <p className="muted">
          {labels[type][1]}
        </p>

        {/* =================================================
            RECIPIENT
        ================================================= */}

        {type === "transfer" && (
          <div className="recipient-section">

            <label>
              Recipient
            </label>

            {!selectedRecipient ? (

              <>

                {/* -----------------------------------------
                    SEARCH BOX
                ----------------------------------------- */}

                <div className="search-box">

                  <Search
                    size={18}
                  />

                  <input
                    value={
                      recipientQuery
                    }
                    onChange={(
                      event
                    ) =>
                      setRecipientQuery(
                        event.target.value
                      )
                    }
                    placeholder="Search by name or email"
                    autoComplete="off"
                  />

                </div>

                {/* -----------------------------------------
                    SEARCHING
                ----------------------------------------- */}

                {searching && (
                  <div className="search-status">
                    Searching...
                  </div>
                )}

                {/* -----------------------------------------
                    NO RESULTS
                ----------------------------------------- */}

                {!searching &&
                  recipientQuery.trim()
                    .length >= 3 &&
                  recipients.length ===
                    0 && (
                    <div className="search-status">
                      No PayFlow users found.
                    </div>
                  )}

                {/* -----------------------------------------
                    RESULTS
                ----------------------------------------- */}

                {recipients.length >
                  0 && (

                  <div className="recipient-results">

                    {recipients.map(
                      (recipient) => (

                        <button
                          type="button"
                          className="recipient-result"
                          key={
                            recipient.user_id ||
                            recipient.id ||
                            recipient.wallet_id
                          }
                          onClick={() =>
                            selectRecipient(
                              recipient
                            )
                          }
                        >

                          <div className="recipient-avatar">

                            {recipient.first_name
                              ?.charAt(0)
                              .toUpperCase()}

                          </div>

                          <div>

                            <strong>

                              {
                                recipient.first_name
                              }{" "}

                              {
                                recipient.last_name
                              }

                            </strong>

                            <span>

                              {
                                recipient.email
                              }

                            </span>

                          </div>

                        </button>

                      )
                    )}

                  </div>
                )}

              </>

            ) : (

              /* -------------------------------------------
                 SELECTED RECIPIENT
              ------------------------------------------- */

              <div className="selected-recipient">

                <div className="recipient-avatar">

                  {selectedRecipient.first_name
                    ?.charAt(0)
                    .toUpperCase()}

                </div>

                <div>

                  <strong>

                    {
                      selectedRecipient.first_name
                    }{" "}

                    {
                      selectedRecipient.last_name
                    }

                  </strong>

                  <span>

                    {
                      selectedRecipient.email
                    }

                  </span>

                </div>

                <CheckCircle2
                  size={20}
                />

                <button
                  type="button"
                  className="link"
                  onClick={() =>
                    setSelectedRecipient(
                      null
                    )
                  }
                >
                  Change
                </button>

              </div>

            )}

          </div>
        )}

        {/* =================================================
            FORM
        ================================================= */}

        <form
          onSubmit={submit}
        >

          {/* ---------------------------------------------
              AMOUNT
          --------------------------------------------- */}

          <label>

            Amount (INR)

            <input
              required
              min="0.01"
              step="0.01"
              type="number"
              value={amount}
              onChange={(event) =>
                setAmount(
                  event.target.value
                )
              }
              placeholder="0.00"
            />

          </label>

          {/* ---------------------------------------------
              DESCRIPTION
          --------------------------------------------- */}

          <label>

            Description

            <input
              value={desc}
              onChange={(event) =>
                setDesc(
                  event.target.value
                )
              }
              placeholder="Optional note"
              maxLength={500}
            />

          </label>

          {/* ---------------------------------------------
              SUBMIT
          --------------------------------------------- */}

          <button
            type="submit"
            className="primary"
            disabled={
              loading ||
              (
                type === "transfer" &&
                !selectedRecipient
              )
            }
          >

            {loading
              ? "Processing..."
              : type === "transfer"
              ? "Review transfer"
              : labels[type][0]}

          </button>

        </form>

        {/* =================================================
            BALANCE
        ================================================= */}

        {wallet && (
          <p className="fine">

            Available balance:{" "}

            {money(
              wallet.available_balance
            )}

          </p>
        )}

        {/* =================================================
            INFO
        ================================================= */}

        <p className="fine">

          Amounts are stored as
          integer paise. Each
          money-moving request receives
          a unique idempotency key.

        </p>

      </div>

    </div>
  );
}

/* =========================================================
   REACT MOUNT
========================================================= */

createRoot(
  document.getElementById("root")
).render(
  <App />
);
