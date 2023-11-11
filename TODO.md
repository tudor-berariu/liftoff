# Liftoff - ToDos

## 1. General

 - [ ] Revise MANIFEST
 - [ ] Show the last commit from liftoff
 - [ ] Show the last commit from current folder (if in a git repo)
 

## 2. liftoff-prepare

 - [ ] Implement '->', '<=>', '^', 'v' for value pairs.

## 3. liftoff

 - [ ] Implement server / client


# Windows Compatibility

0. verificăm să meargă `liftoff script.py ./configs/test--dev.yaml`
1. confirmăm că `liftoff-prepare` produce structura de directoare dorită DONE
2. confirmăm că `liftoff-status` funcționează (afișează corect tabelul ăla)
3. testăm că lansarea de procese funcționează, adică `liftoff script.py ./results/un_experiment_generat_de_liftoff-prepare/` ...
4. verificăm restul lucrurilor mai puțin esențiale, precum liftoff-procs și liftoff-abort.