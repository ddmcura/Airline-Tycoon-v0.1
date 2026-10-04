"""Private, bounded read capabilities and write capsules for certified transitions.

No raw candidate node is returned by the handler-facing read API. This is an ordinary Python API
boundary, not a sandbox against deliberate Python reflection or monkeypatching.
Canonical world/alias validators and detached publication remain independent.
"""
from copy import deepcopy
from weakref import ref
import json
from collections.abc import Mapping, Sequence

from game.world_state.serialization import json_compatibility_error
def mutable_alias_error(value):
    from game.world_state.validation import _container_alias_error
    return _container_alias_error(value)



def _deny(*args, **kwargs):
    raise ValueError('certified mutation boundary: protected read-only authority')


class ReadOnlyDict(Mapping):
    __slots__ = ('_access',)
    def __init__(self, values, *, _wrap=None):
        if hasattr(self, '_access'): _deny()
        wrap = _wrap or _view_factory({})
        # Only this capability is stored. It never returns a raw mutable node.
        # Deliberate function-closure introspection is outside this Python API.
        def access(operation, key=None):
            wrap(None)
            if operation == 'get': return wrap(values[key])
            if operation == 'keys': return iter(values)
            return len(values)
        object.__setattr__(self, '_access', access)
    __delattr__ = __setattr__ = __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _deny
    def __getitem__(self, key): return self._access('get', key)
    def __iter__(self): return self._access('keys')
    def __len__(self): return self._access('len')
    def __deepcopy__(self, memo):
        return {deepcopy(k, memo): deepcopy(v, memo) for k, v in self.items()}


class ReadOnlyList(Sequence):
    __slots__ = ('_access',)
    def __init__(self, values, *, _wrap=None):
        if hasattr(self, '_access'): _deny()
        if type(values) not in (list, tuple): values=tuple(values)
        wrap = _wrap or _view_factory({})
        def access(operation, key=None):
            wrap(None)
            if operation == 'get' and isinstance(key,slice):
                return ReadOnlyList(values[key],_wrap=wrap)
            return wrap(values[key]) if operation == 'get' else len(values)
        object.__setattr__(self, '_access', access)
    __delattr__ = __setattr__ = __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _deny
    def __getitem__(self, index): return self._access('get', index)
    def __len__(self): return self._access('len')
    def __eq__(self, other):
        if type(other) not in (list, ReadOnlyList): return NotImplemented
        return len(self) == len(other) and all(a == b for a, b in zip(self, other))
    def __deepcopy__(self, memo):
        return [deepcopy(v, memo) for v in self]


def _view_factory(cache, alive=None):
    def wrap(value):
        if alive is not None and not alive[0]:
            raise ValueError('ownership read capability expired')
        if type(value) in (ReadOnlyDict,ReadOnlyList): return value
        if value is None or type(value) in (str,bool,int,float): return value
        if type(value) not in (dict,list):
            raise ValueError('unsupported ownership read type')
        marker=id(value)
        existing=cache.get(marker)
        if existing is not None:
            if existing[0] is not value: raise ValueError('ownership reference identity reused')
            return existing[1]
        view=(ReadOnlyDict(value,_wrap=wrap) if type(value) is dict else ReadOnlyList(value,_wrap=wrap))
        # Strong source references prevent identity reuse during this bounded
        # candidate. Close clears the memo before commit/recovery. This memo
        # reuses capabilities; it is never an alias proof or authority index.
        cache[marker]=(value,view)
        return view
    return wrap


def is_read_dict(value):
    return type(value) in (dict, ReadOnlyDict)



class _WriteTable(dict):
    def __init__(self, base, keys):
        super().__init__(base)
        self._keys = frozenset(keys)
        for key in self._keys:
            if key in self:
                dict.__setitem__(self, key, deepcopy(self[key]))

    def __setitem__(self, key, value):
        if key not in self._keys:
            raise ValueError('certified mutation boundary: unapproved record')
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        if key not in self._keys:
            raise ValueError('certified mutation boundary: unapproved deletion')
        dict.__delitem__(self, key)

    clear = popitem = __ior__ = _deny

    def pop(self, key, *default):
        if key in self:
            value = self[key]; del self[key]; return value
        if default: return default[0]
        raise KeyError(key)

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items(): self[key] = value

    def setdefault(self, key, default=None):
        if key not in self: self[key] = default
        return self[key]


_OWNERSHIP_TOKEN = object()


def require_capsule(ownership, envelope):
    if type(ownership) is not WriteCapsule or ownership._token is not _OWNERSHIP_TOKEN:
        raise ValueError('unrecognized ownership capability')
    ownership.require_envelope(envelope)


def require_predecessor(ownership, envelope):
    """Trusted proof capture may read original authority; handlers never receive it."""
    require_capsule(ownership, ownership.envelope)
    if envelope is not ownership.envelope and id(envelope) != ownership._source_identity:
        raise ValueError('ownership witness belongs to another predecessor')


class WriteCapsule:
    """One-event writable copies, with protected root identities sealed."""
    def __init__(self, snapshot, footprint, *, _token=None, _alive=None, _source_identity=None):
        if _token is not _OWNERSHIP_TOKEN or type(snapshot) is not ReadOnlyDict:
            raise ValueError('ownership capsules require private candidate construction')
        self._token = _token
        self._alive = _alive
        self._consumed = False
        self._snapshot = snapshot
        self._source_identity = _source_identity
        self.footprint = {name: frozenset(keys) for name, keys in footprint.items()}
        self.envelope = dict(snapshot)
        self.envelope['world_state'] = dict(snapshot['world_state'])
        self.envelope['simulation'] = deepcopy(snapshot['simulation'])
        self.envelope['deterministic_state'] = dict(snapshot['deterministic_state'])
        self.envelope['deterministic_state']['id_allocator'] = deepcopy(snapshot['deterministic_state']['id_allocator'])
        for name, keys in self.footprint.items():
            self.envelope['world_state'][name] = _WriteTable(snapshot['world_state'][name], keys)
        self._roots = dict(self.envelope)
        self._world_roots = dict(self.envelope['world_state'])
        self._det_roots = dict(self.envelope['deterministic_state'])

    def require_envelope(self, envelope):
        if self._consumed or self._alive is None or not self._alive[0]:
            raise ValueError('ownership write capability expired')
        if envelope is not self.envelope:
            raise ValueError('ownership proof belongs to another transition')

    def checked_outputs(self):
        self.require_envelope(self.envelope)
        def sealed(actual, expected):
            if type(actual) is not dict or actual.keys() != expected.keys() or any(actual[k] is not v for k, v in expected.items()):
                raise ValueError('certified mutation boundary: replaced protected root')
        sealed(self.envelope, self._roots)
        sealed(self.envelope['world_state'], self._world_roots)
        sealed(self.envelope['deterministic_state'], self._det_roots)
        records = {}
        for name, keys in self.footprint.items():
            table = self.envelope['world_state'][name]
            # Also detects a base-class insertion outside the normal table API.
            base = self._snapshot['world_state'][name]
            if table._keys != keys or set(table) - keys != set(base) - keys:
                raise ValueError('certified mutation boundary: changed key topology')
            if any(table[key] is not row for key, row in base.items() if key not in keys):
                raise ValueError('certified mutation boundary: replaced protected record')
            records[name] = {key: table[key] for key in keys if key in table}
        outputs = {'simulation': self.envelope['simulation'],
                   'allocator': self.envelope['deterministic_state']['id_allocator'],
                   'records': records}
        error = json_compatibility_error(outputs)
        if error: raise ValueError(f'non-JSON ownership output: {error}')
        if mutable_alias_error(outputs):
            raise ValueError('authoritative mutable-container alias in ownership output')
        return outputs


class CandidateOwnership:
    """Validated candidate read capabilities; never kept across step()."""
    def __init__(self, candidate, *, _validated=False):
        # Standalone construction is fail-closed. The resolver alone supplies
        # _validated after full validation and an alias-preserving detached clone,
        # or a full-gated probe. Never infer validity from revisions/identity.
        if not _validated:
            if mutable_alias_error(candidate): raise ValueError('invalid ownership alias baseline')
            error=json_compatibility_error(candidate)
            if error: raise ValueError(f'non-JSON ownership baseline: {error}')
        self._candidate = candidate
        self._views = {}
        self._read_lookups = {}
        self._alive = [True]
        self._snapshot = _view_factory(self._views,self._alive)(candidate)

    def begin(self, footprint, *, read_lookup_factory=None):
        if not self._alive[0]: raise ValueError('ownership candidate expired')
        # Also protect an existing service from a later mixed-handler footprint.
        for factory in self._read_lookups:
            if set(footprint).intersection(factory.protected_collections):
                raise ValueError('candidate lookup source is writable')
        if read_lookup_factory is not None and set(footprint).intersection(read_lookup_factory.protected_collections):
            raise ValueError('candidate lookup source is writable')
        capsule = WriteCapsule(self._snapshot, footprint, _token=_OWNERSHIP_TOKEN,
                              _alive=self._alive, _source_identity=id(self._candidate))
        capsule_ref = ref(capsule)
        def read(envelope, key):
            # Avoid a capsule -> callback -> capsule cycle retaining event copies.
            bound = capsule_ref()
            if bound is None: raise ValueError('ownership read capability expired')
            require_predecessor(bound, envelope)
            if envelope is bound.envelope:
                for name in read_lookup_factory.protected_collections:
                    if envelope['world_state'][name] is not bound._world_roots[name]:
                        raise ValueError('candidate lookup source replaced')
            service = self._read_lookups.get(read_lookup_factory)
            if service is None:
                service = read_lookup_factory(self._candidate)
                self._read_lookups[read_lookup_factory] = service
            return service.lookup(envelope, key)
        capsule.read_lookup = read if read_lookup_factory is not None else None
        return capsule

    def close(self):
        self._alive[0] = False
        for service in self._read_lookups.values(): service.close()
        self._read_lookups.clear()
        self._views.clear()
        self._candidate = self._snapshot = None

    def publish(self, candidate, capsule):
        if capsule._snapshot is not self._snapshot:
            raise ValueError('ownership capsule belongs to another candidate')
        if candidate is not self._candidate:
            raise ValueError('ownership publication belongs to another candidate')
        validated = capsule.checked_outputs()
        def encoded(value):
            return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
        expected = encoded(validated)
        outputs = deepcopy(validated)
        candidate['simulation'] = outputs['simulation']
        candidate['deterministic_state']['id_allocator'] = outputs['allocator']
        for name, keys in capsule.footprint.items():
            target = candidate['world_state'][name]
            for key in keys:
                if key in outputs['records'][name]:
                    row = outputs['records'][name][key]
                    target[key] = row
                else:
                    target.pop(key, None)

        # Independent local bridge: compare actual inserted authority with the
        # validated transaction serialized BEFORE detaching/publication. The read
        # facade follows the same private candidate; it is not a second authority.
        actual = {'simulation': candidate['simulation'],
                  'allocator': candidate['deterministic_state']['id_allocator'],
                  'records': {name: {key: candidate['world_state'][name][key]
                              for key in keys if key in candidate['world_state'][name]}
                              for name, keys in capsule.footprint.items()}}
        if encoded(actual) != expected:
            raise ValueError('ownership publication divergence')
        capsule._consumed = True
