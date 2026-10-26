% DUMP_RING  Export the AT lattice (THERING) of an MML session as JSON.
%
% Writes <prefix>_ring.json: a list with one object per element, in
% THERING order (the AO's ATIndex / ATParameterGroup ElemIndex are 1-based
% indices into it), with every field of the element (FamName, PassMethod,
% Length, PolynomA/B, BendingAngle, Frequency, ... as the lattice has them;
% NaN as null, 6x6 matrices as nested lists), plus "Index" (1-based) and
% "Class" where AT's atguessclass can tell it.
%
% Same environment as ao_oracle.m (see mml_session.m):
%   MML_ROOT=... MML_MACHINE=ALS MML_SUBMACHINE=StorageRing MML_MODE=1 \
%     matlab -batch dump_ring

cfg = mml_session();
global THERING
ring = cell(1, numel(THERING));
has_guess = exist('atguessclass', 'file') == 2;
for i = 1:numel(THERING)
  e = THERING{i};
  e.Index = i;
  if ~isfield(e, 'Class') && has_guess
    try, e.Class = atguessclass(THERING{i}); catch, end
  end
  ring{i} = e;
end
mml_write_json([cfg.prefix '_ring.json'], ring);
fprintf('%s: %d elements, energy %g GeV\n', cfg.prefix, numel(THERING), getenergy('Model'));
