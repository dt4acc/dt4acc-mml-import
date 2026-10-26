function mml_write_json(name, v)
% MML_WRITE_JSON  Write a middle layer value (see mml_sanitize) as JSON.
fid = fopen(name, 'w');
if fid < 0, error('mml_write_json:open', 'cannot write %s', name); end
fprintf(fid, '%s', jsonencode(mml_sanitize(v)));
fclose(fid);
fprintf('wrote %s\n', name);
end
