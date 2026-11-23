import React, { useState, useEffect } from 'react';
import { request, getUserFromToken } from './api';

const can = (role, action) => {
  const matrix = {
    admin:  ['viewOrders', 'editOrder', 'deleteOrder', 'manageUnits', 'manageStorage',
             'manageBreads', 'viewClients', 'viewAnalytics', 'seedTest', 'createOrder'],
    worker: ['viewOrders', 'editOrder', 'manageUnits', 'manageStorage', 'createOrder'],
    user:   ['createOrder', 'viewOwnOrders', 'viewOwnAnalytics'],
  };
  return (matrix[role] || []).includes(action);
};

function AuthForm({ onLogin }) {
  const [isReg, setIsReg] = useState(false);
  
  // Переменная f восстановлена (без неё была ошибка "f is not defined")
  const [f, setF] = useState({
    contact_info: '',
    client_name: '',
    password: '',
    favorite_bread: '',
  });

  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (isReg) {
        await request('/register', 'POST', {
          contact_info: f.contact_info,
          client_name: f.client_name,
          password: f.password,
          favorite_bread: f.favorite_bread || null,
        });
      }
      const body = new URLSearchParams();
      body.append('username', f.contact_info);
      body.append('password', f.password);

      const data = await request('/login', 'POST', body, true);
      localStorage.setItem('token', data.access_token);
      onLogin(getUserFromToken(data.access_token));
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="container mt-5" style={{ maxWidth: 400 }}>
      <div className="card shadow-sm">
        <div className="card-body p-4">
          <h4 className="text-center mb-3">{isReg ? 'Регистрация' : 'Вход'}</h4>
          <form onSubmit={submit}>
            <input
              className="form-control mb-2"
              placeholder="Контакт (логин)"
              required
              value={f.contact_info}
              onChange={(e) => set('contact_info', e.target.value)}
            />
            {isReg && (
              <>
                <input
                  className="form-control mb-2"
                  placeholder="Имя"
                  required
                  value={f.client_name}
                  onChange={(e) => set('client_name', e.target.value)}
                />
                <input
                  className="form-control mb-2"
                  placeholder="Любимый хлеб (необяз.)"
                  value={f.favorite_bread}
                  onChange={(e) => set('favorite_bread', e.target.value)}
                />
              </>
            )}
            <input
              type="password"
              className="form-control mb-3"
              placeholder="Пароль"
              required
              value={f.password}
              onChange={(e) => set('password', e.target.value)}
            />
            <button className="btn btn-primary w-100">
              {isReg ? 'Зарегистрироваться' : 'Войти'}
            </button>
          </form>
          <button
            className="btn btn-link btn-sm w-100 mt-2"
            onClick={() => setIsReg(!isReg)}
          >
            {isReg ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Регистрация'}
          </button>
        </div>
      </div>
    </div>
  );
}


function useBreads() {
  const [breads, setBreads] = useState([]);
  useEffect(() => {
    request('/breads').then(setBreads).catch(() => setBreads([]));
  }, []);
  return [breads, setBreads];
}

function OrderForm({ breads, onCreated }) {
  const [f, setF] = useState({
    fiskal_doc: '',
    bread_type: '',
    size: 1,
    payment_date: '2026-11-23',
  });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    try {
      await request('/orders/my', 'POST', {
        fiskal_doc: f.fiskal_doc,
        bread_type: f.bread_type || breads[0]?.type,
        size: Number(f.size),
        payment_date: f.payment_date,
      });
      setF({ ...f, fiskal_doc: '' });
      onCreated();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <form className="row g-2 mb-4" onSubmit={submit}>
      <div className="col-md-3">
        <input
          className="form-control"
          placeholder="Чек (FD-01)"
          maxLength={10}
          required
          value={f.fiskal_doc}
          onChange={(e) => set('fiskal_doc', e.target.value)}
        />
      </div>
      <div className="col-md-3">
        <select
          className="form-select"
          value={f.bread_type}
          onChange={(e) => set('bread_type', e.target.value)}
        >
          {breads.map((b) => (
            <option key={b.type} value={b.type}>
              {b.type} — {b.selling_cost} ₽
            </option>
          ))}
        </select>
      </div>
      <div className="col-md-2">
        <input
          type="number"
          min={1}
          className="form-control"
          value={f.size}
          onChange={(e) => set('size', e.target.value)}
        />
      </div>
      <div className="col-md-2">
        <input
          type="date"
          className="form-control"
          value={f.payment_date}
          onChange={(e) => set('payment_date', e.target.value)}
        />
      </div>
      <div className="col-md-2">
        <button className="btn btn-success w-100">Заказать</button>
      </div>
    </form>
  );
}

function OrdersTable({ orders, role, onRefresh }) {
  const editOrder = async (o) => {
    const unit = prompt('ID цеха:', o.unit_responsible ?? '');
    if (unit === null) return;
    const stor = prompt('ID склада:', o.stored_at ?? '');
    if (stor === null) return;
    try {
      await request(`/orders/${o.fiskal_doc}`, 'PATCH', {
        unit_responsible: unit ? Number(unit) : null,
        stored_at: stor ? Number(stor) : null,
      });
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  const remove = async (o) => {
    if (!confirm(`Удалить заказ ${o.fiskal_doc}?`)) return;
    try {
      await request(`/orders/${o.fiskal_doc}`, 'DELETE');
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <table className="table table-bordered table-sm">
      <thead className="table-light">
        <tr>
          <th>Чек</th>
          <th>Клиент</th>
          <th>Хлеб</th>
          <th>Кол-во</th>
          <th>Цех</th>
          <th>Склад</th>
          <th>Сумма</th>
          {(can(role, 'editOrder') || can(role, 'deleteOrder')) && <th>Действия</th>}
        </tr>
      </thead>
      <tbody>
        {orders.map((o) => (
          <tr key={o.fiskal_doc}>
            <td>{o.fiskal_doc}</td>
            <td>{o.client_contacts}</td>
            <td>{o.bread_type}</td>
            <td>{o.size}</td>
            <td>{o.unit_responsible ?? '-'}</td>
            <td>{o.stored_at ?? '-'}</td>
            <td>{o.payment_size} ₽</td>
            {(can(role, 'editOrder') || can(role, 'deleteOrder')) && (
              <td>
                {can(role, 'editOrder') && (
                  <button className="btn btn-warning btn-sm me-1" onClick={() => editOrder(o)}>
                    Изм.
                  </button>
                )}
                {can(role, 'deleteOrder') && (
                  <button className="btn btn-danger btn-sm" onClick={() => remove(o)}>
                    Уд.
                  </button>
                )}
              </td>
            )}
          </tr>
        ))}
        {orders.length === 0 && (
          <tr>
            <td colSpan={8} className="text-center text-muted">Нет заказов</td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function UnitsPanel({ onRefresh }) {
  const [units, setUnits] = useState([]);
  const [f, setF] = useState({ id: '', employee_responsible: '', flour_left: '' });

  const load = () => request('/units').then(setUnits).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await request('/units', 'POST', {
        id: Number(f.id),
        employee_responsible: f.employee_responsible,
        flour_left: Number(f.flour_left),
      });
      setF({ id: '', employee_responsible: '', flour_left: '' });
      load();
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="mb-4">
      <h5>Цеха</h5>
      <form className="row g-2 mb-2" onSubmit={submit}>
        <div className="col-2">
          <input
            className="form-control form-control-sm"
            placeholder="ID"
            required
            value={f.id}
            onChange={(e) => setF({ ...f, id: e.target.value })}
          />
        </div>
        <div className="col">
          <input
            className="form-control form-control-sm"
            placeholder="Ответственный"
            required
            value={f.employee_responsible}
            onChange={(e) => setF({ ...f, employee_responsible: e.target.value })}
          />
        </div>
        <div className="col-2">
          <input
            className="form-control form-control-sm"
            placeholder="Мука"
            required
            value={f.flour_left}
            onChange={(e) => setF({ ...f, flour_left: e.target.value })}
          />
        </div>
        <div className="col-auto">
          <button className="btn btn-success btn-sm">Добавить</button>
        </div>
      </form>
      <table className="table table-sm table-bordered">
        <thead className="table-light">
          <tr>
            <th>ID</th>
            <th>Ответственный</th>
            <th>Мука</th>
          </tr>
        </thead>
        <tbody>
          {units.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.employee_responsible}</td>
              <td>{u.flour_left}</td>
            </tr>
          ))}
          {units.length === 0 && (
            <tr>
              <td colSpan={3} className="text-center text-muted">Пусто</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function StoragePanel({ onRefresh }) {
  const [items, setItems] = useState([]);
  const [f, setF] = useState({ id: '', spaces_left: '' });

  const load = () => request('/storage').then(setItems).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await request('/storage', 'POST', { id: Number(f.id), spaces_left: Number(f.spaces_left) });
      setF({ id: '', spaces_left: '' });
      load();
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="mb-4">
      <h5>Склады</h5>
      <form className="row g-2 mb-2" onSubmit={submit}>
        <div className="col-2">
          <input
            className="form-control form-control-sm"
            placeholder="ID"
            required
            value={f.id}
            onChange={(e) => setF({ ...f, id: e.target.value })}
          />
        </div>
        <div className="col-3">
          <input
            className="form-control form-control-sm"
            placeholder="Мест свободно"
            required
            value={f.spaces_left}
            onChange={(e) => setF({ ...f, spaces_left: e.target.value })}
          />
        </div>
        <div className="col-auto">
          <button className="btn btn-success btn-sm">Добавить</button>
        </div>
      </form>
      <table className="table table-sm table-bordered">
        <thead className="table-light">
          <tr>
            <th>ID</th>
            <th>Мест свободно</th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td>{s.spaces_left}</td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={2} className="text-center text-muted">Пусто</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function AdminPanel({ currentContact, onRefresh }) {
  const [clients, setClients] = useState([]);
  const [analytics, setAnalytics] = useState([]);
  const [f, setF] = useState({ type: '', creation_cost: '', selling_cost: '', test_n: 5 });

  const load = async () => {
    request('/admin/clients').then(setClients).catch(() => {});
    request('/analytics/spent-on-fav').then(setAnalytics).catch(() => {});
  };
  
  useEffect(() => {
    load();
  }, []);

  const addBread = async (e) => {
    e.preventDefault();
    try {
      await request('/admin/breads', 'POST', {
        type: f.type,
        creation_cost: Number(f.creation_cost),
        selling_cost: Number(f.selling_cost),
      });
      setF({ ...f, type: '', creation_cost: '', selling_cost: '' });
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  const seed = async () => {
    try {
      const res = await request('/admin/test-clients/seed', 'POST', { n: Number(f.test_n) });
      alert(res.detail);
      load();
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  const wipe = async () => {
    if (!confirm('Удалить всех тестовых клиентов?')) return;
    try {
      const res = await request('/admin/test-clients', 'DELETE');
      alert(res.detail);
      load();
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <>
      <h5>Добавить сорт хлеба</h5>
      <form className="row g-2 mb-4" onSubmit={addBread}>
        <div className="col">
          <input
            className="form-control form-control-sm"
            placeholder="Название"
            required
            value={f.type}
            onChange={(e) => setF({ ...f, type: e.target.value })}
          />
        </div>
        <div className="col">
          <input
            className="form-control form-control-sm"
            placeholder="Себестоимость"
            required
            value={f.creation_cost}
            onChange={(e) => setF({ ...f, creation_cost: e.target.value })}
          />
        </div>
        <div className="col">
          <input
            className="form-control form-control-sm"
            placeholder="Цена продажи"
            required
            value={f.selling_cost}
            onChange={(e) => setF({ ...f, selling_cost: e.target.value })}
          />
        </div>
        <div className="col-auto">
          <button className="btn btn-primary btn-sm">Добавить</button>
        </div>
      </form>

      <h5>Хранимые процедуры</h5>
      <div className="d-flex gap-2 mb-4 align-items-center">
        <input
          type="number"
          className="form-control form-control-sm"
          style={{ width: 80 }}
          value={f.test_n}
          onChange={(e) => setF({ ...f, test_n: e.target.value })}
        />
        <button className="btn btn-primary btn-sm" onClick={seed}>
          Создать тестовых
        </button>
        <button className="btn btn-danger btn-sm" onClick={wipe}>
          Удалить тестовых
        </button>
      </div>

      <h5>Пользователи</h5>
      <table className="table table-sm table-bordered mb-4 align-middle">
        <thead className="table-light">
          <tr>
            <th>Контакт</th>
            <th>Имя</th>
            <th>Любимый хлеб</th>
            <th style={{ width: 160 }}>Роль</th>
          </tr>
        </thead>
        <tbody>
          {clients.map((c) => (
            <tr key={c.contact_info}>
              <td>{c.contact_info}</td>
              <td>{c.client_name}</td>
              <td>{c.favorite_bread || '-'}</td>
              <td>
                {c.contact_info === currentContact ? (
                  <span className="badge bg-secondary">{c.status} (вы)</span>
                ) : (
                  <select
                    className="form-select form-select-sm"
                    value={c.status}
                    onChange={async (e) => {
                      const newRole = e.target.value;
                      if (newRole === c.status) return;
                      try {
                        await request(`/admin/clients/${c.contact_info}`, 'PATCH', {
                          status: newRole,
                        });
                        load();
                      } catch (err) {
                        alert(err.message);
                        e.target.value = c.status; // откатить обратно при ошибке
                      }
                    }}
                  >
                    <option value="user">user</option>
                    <option value="worker">worker</option>
                    <option value="admin">admin</option>
                  </select>
                )}
              </td>
            </tr>
          ))}
          {clients.length === 0 && (
            <tr>
              <td colSpan={4} className="text-center text-muted">Нет пользователей</td>
            </tr>
          )}
        </tbody>
      </table>

      <h5>Аналитика</h5>
      <table className="table table-sm table-bordered mb-4">
        <thead className="table-light">
          <tr>
            <th>Клиент</th>
            <th>Любимый хлеб</th>
            <th>Потрачено</th>
          </tr>
        </thead>
        <tbody>
          {analytics.map((s) => (
            <tr key={s.client}>
              <td>{s.client}</td>
              <td>{s.fav_bread || '-'}</td>
              <td>{s.spent} ₽</td>
            </tr>
          ))}
          {analytics.length === 0 && (
            <tr>
              <td colSpan={3} className="text-center text-muted">Нет данных</td>
            </tr>
          )}
        </tbody>
      </table>
    </>
  );
}

export default function App() {
  const [user, setUser] = useState(() => getUserFromToken(localStorage.getItem('token')));
  const [orders, setOrders] = useState([]);
  const [breads] = useBreads();

  const reloadOrders = () => request('/orders').then(setOrders).catch(() => {});

  useEffect(() => {
    if (user) reloadOrders();
  }, [user]);

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
    setOrders([]);
  };

  if (!user) return <AuthForm onLogin={setUser} />;

  return (
    <div className="container py-4">
      {/* Header */}
      <div className="d-flex justify-content-between align-items-center mb-4 p-3 bg-dark text-white rounded">
        <div>
          <strong>Хлебозавод</strong> | {user.contact}{' '}
          <span className="badge bg-warning text-dark">{user.role}</span>
        </div>
        <button className="btn btn-outline-light btn-sm" onClick={logout}>
          Выйти
        </button>
      </div>

      {can(user.role, 'createOrder') && (
        <>
          <h5>Сделать заказ</h5>
          <OrderForm breads={breads} onCreated={reloadOrders} />
        </>
      )}

      {/* Orders */}
      <h5>Заказы</h5>
      <OrdersTable orders={orders} role={user.role} onRefresh={reloadOrders} />

      {/* Worker/Admin: units + storage */}
      {can(user.role, 'manageUnits') && (
        <>
          <UnitsPanel onRefresh={reloadOrders} />
          <StoragePanel onRefresh={reloadOrders} />
        </>
      )}

      {can(user.role, 'manageBreads') && (
        <AdminPanel currentContact={user.contact} onRefresh={reloadOrders} />
      )}
    </div>
  );
}