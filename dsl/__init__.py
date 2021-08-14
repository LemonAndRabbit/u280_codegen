lan = """
Program:
(
    ('ITERATE' ':' iterate=INT)
    ('KERNEL' ':' app_name=ID)
    ('COUNT' ':' kernel_count=INT)
    (input_stmts=InputStmt)+
    (output_stmt=OutputStmt)
)#;

Comment: /\/\/.*$/;

InputStmt: 'input' name=ID '(' size=INT (',' size=INT)* ')'; //now all inputs&outputs are forced to be float value

OutputStmt: 'output' (let=Let)* ref=Ref '=' expr=Expr;//now all inputs&outputs are forced to be float value

//Specify Expressions
Num: INT | FLOAT;

FuncName: 'fabs' | 'abs'; //more functions to be added

Let: name=ID '=' expr=Expr;
Ref: name=ID '(' idx=INT (',' idx=INT)* ')';

Expr: operand=LogicAnd (operator=LogicOrOp operand=LogicAnd)*;
LogicOrOp: '||';

LogicAnd: operand=BinaryOr (operator=LogicAndOp operand=BinaryOr)*;
LogicAndOp: '&&';

BinaryOr: operand=Xor (operator=BinaryOrOp operand=Xor)*;
BinaryOrOp: '|';

Xor: operand=BinaryAnd (operator=XorOp operand=BinaryAnd)*;
XorOp: '^';

BinaryAnd: operand=EqCmp (operator=BinaryAndOp operand=EqCmp)*;
BinaryAndOp: '&';

EqCmp: operand=LtCmp (operator=EqCmpOp operand=LtCmp)*;
EqCmpOp: '=='|'!=';

LtCmp: operand=AddSub (operator=LtCmpOp operand=AddSub)*;
LtCmpOp: '<='|'>='|'<'|'>';

AddSub: operand=MulDiv (operator=AddSubOp operand=MulDiv)*;
AddSubOp: '+'|'-';

MulDiv: operand=Unary (operator=MulDivOp operand=Unary)*;
MulDivOp: '*'|'/'|'%';

Unary: (operator=UnaryOp)* operand=Operand;
UnaryOp: '+'|'-'|'~'|'!';

Operand: call=Call | ref=Ref | num=Num | '(' expr=Expr ')' | var=Var;
Call: name=FuncName '(' arg=Expr (',' arg=Expr)* ')';
Var: name=ID;
"""