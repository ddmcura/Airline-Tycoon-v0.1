"""Exact runtime-only flight witnesses; never a save format or input decoder.

Untouched authority remains fully compared: certified handlers receive mutable
references, so neither object identity nor revisions prove non-mutation. The C
codec replaces repeated JSON sorting/hashing. Separate whole-candidate alias
checking is mandatory because the value codec deliberately disables its memo.
"""
import io
import pickle


class _ValuePickler(pickle.Pickler):
    def reducer_override(self, value):
        # Never execute a custom object's reduction while proving authority.
        raise ValueError('flight introduced non-JSON authority: non-plain object')


def protected_bytes(value):
    """Detached exact typed value bytes, with no mutable references retained.

    Memo suppression makes primitive sharing irrelevant and preserves all value
    types (unlike JSON key/tuple coercion). Dictionary order is preserved: an
    unexpected reordering conservatively rejects, never accepts a bad event.
    Cycles fail closed. These bytes are compared only, never decoded.
    """
    output = io.BytesIO()
    encoder = _ValuePickler(output, protocol=5)
    encoder.fast = True
    encoder.dump(value)
    return output.getvalue()


def mutable_alias_error(value):
    """Same exact dict/list alias predicate, without constructing unused paths.

    Visit every mutable container, including cross-record/protected aliases.
    Primitive leaves cannot alias mutable authority; skip their path/stack work.
    Full diagnostics remain available through the canonical validator on failure.
    """
    if type(value) not in (dict, list):
        return None
    seen = set()
    stack = [value]
    while stack:
        item = stack.pop()
        marker = id(item)
        if marker in seen:
            return 'repeated mutable container'
        seen.add(marker)
        values = item.values() if type(item) is dict else item
        stack.extend(nested for nested in values if type(nested) in (dict, list))
    return None
