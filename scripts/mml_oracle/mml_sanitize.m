function v = mml_sanitize(v)
% MML_SANITIZE  Make a middle layer value JSON encodable.
%
% Function handles become their text (func2str), struct arrays cells of
% structs, other objects (e.g. inline) the string '<class name>'. Numbers,
% strings, cells and structs are kept; jsonencode writes NaN as null.
if isa(v, 'function_handle')
  v = func2str(v);
elseif isstruct(v)
  if numel(v) ~= 1
    c = cell(1, numel(v));
    for k = 1:numel(v), c{k} = mml_sanitize(v(k)); end
    v = c;
    return
  end
  fn = fieldnames(v);
  for k = 1:numel(fn), v.(fn{k}) = mml_sanitize(v.(fn{k})); end
elseif iscell(v)
  v = cellfun(@mml_sanitize, v, 'UniformOutput', false);
elseif isobject(v)
  v = ['<' class(v) '>'];
end
end
