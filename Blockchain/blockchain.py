import hashlib
import json
from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse
import requests
import ellipticcurve
from ellipticcurve.ecdsa import Ecdsa
from ellipticcurve.publicKey import PublicKey

from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin

from merkle_tree import findMerkleRoot


class Blockchain(object):

    # Address of the origin
    baseAddress = "-----BEGIN PUBLIC KEY-----\nMFYwEAYHKoZIzj0CAQYFK4EEAAoDQgAE7MTrJ3EZkwF/cz/Hv9OmmK1kI3oRQ4ow\nzqZ0wDQaqMkCSaoNdDgN6Hvj38E0VbwZ0cuEnQmuhMjxBJ61EHwiJQ==\n-----END PUBLIC KEY-----\n"

    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()
        self.UTXO = dict()
        self.merkleroot = None

        # Create the genesis block
        self.new_block(previous_hash=1, proof=100)


    def get_input_transaction(self, sender, recipient, batchID):
        """
        Finds a UTXO where the product is received by sender.
        :param sender: <str> Address of the Sender
        :param recipient: <str> Address of the Recipient
        :param batchID: <int> ID of the product
        :return: <str> hash of the input transaction if found, an empty string if the sender is the baseAddress, and None otherwise
        """

        if sender==Blockchain.baseAddress:
            return ""

        for possible_input in self.UTXO.values():
            if possible_input['recipient'] == sender and possible_input['batchID'] == batchID:
                return self.hash(possible_input)


    def new_block(self, proof, previous_hash=None):
        """
        Create a new Block in the Blockchain
        :param proof: <int> The proof given by the Proof of Work algorithm
        :param previous_hash: (Optional) <str> Hash of previous Block
        :return: <dict> New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),

            # Don't forget to five findMerkleRoot a string!
            'merkleroot': findMerkleRoot(str(self.get_list_transaction_inputs())) 
        }

        # Reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)
        return block


    def get_list_transaction_inputs(self):
        """Returns the list of all transaction inputs in the blockchain.
        NB: A transaction input is a list of single transactions (that 
        can be identified using their batchID).

        Returns:
            list
        """
        list_transaction_inputs = []

        for block in self.chain:
            list_transaction_inputs.append(block['transactions'])

        return list_transaction_inputs


    def get_input_transaction(self, sender, recipient, batchID):
        """
        Finds a UTXO where the product is received by sender.
        :param sender: <str> Address of the Sender
        :param recipient: <str> Address of the Recipient
        :param batchID: <int> ID of the product
        :return: <str> hash of the input transaction if found, an empty string if the sender is the baseAddress, and None otherwise
        """

        if sender==Blockchain.baseAddress:
            return ""

        for possible_input in self.UTXO.values():
            if possible_input['recipient'] == sender and possible_input['batchID'] == batchID:
                return self.hash(possible_input)



    def new_transaction(self, sender, recipient, batchID, transaction_input, signature):
        """
        Creates a new transaction to go into the next mined Block
        :param sender: <str> Address of the Sender
        :param recipient: <str> Address of the Recipient
        :param batchID: <int> ID of the product
        :param transaction_input: <str> Hash of the input transaction
        :param signature: <str> Transaction signature made using the sender's private key
        :return: <int> The index of the Block that will hold this transaction, or None in case of error
        """

        transaction = {
            'sender': sender,
            'recipient': recipient,
            'batchID': batchID,
            'transaction_input':transaction_input,
            'signature':signature
        }

        if sender!=Blockchain.baseAddress:
            if transaction_input in self.UTXO:
                self.UTXO.pop(transaction_input)
            else:
                return Exception("Invalid transaction input")
        self.UTXO[self.hash(transaction)] = transaction
        self.current_transactions.append(transaction)
        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(dictionnary):
        """
        Creates a SHA-256 hash of a dict
        :param block: <dict>
        :return: <str>
        """

        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        dictionnary_string = json.dumps(dictionnary, sort_keys=True).encode()
        return hashlib.sha256(dictionnary_string).hexdigest()


    def proof_of_work(self, last_proof):
        """
        Simple Proof of Work Algorithm:
         - Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
         - p is the previous proof, and p' is the new proof
        :param last_proof: <int>
        :return: <int>
        """
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Validates the Proof: Does hash(last_proof, proof) contain 4 leading zeroes?
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :return: <bool> True if correct, False if not.
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def valid_signature(self, transaction):
        """
        Validates the transaction signature : was the transaction really created by the sender ?
        :param transaction: <dict>
        :return: <bool>
        """
        transaction_copy = transaction.copy() # les dictionnaires sont passés par référence
        signature = transaction_copy.pop("signature")
        ecdsa_signature = ellipticcurve.signature.Signature.fromBase64(signature)
        key = transaction_copy['sender']
        ecdsa_key = PublicKey.fromPem(key)
        try:
            return Ecdsa.verify(self.hash(transaction_copy), ecdsa_signature, ecdsa_key)
        except:
            return False

    def register_node(self, address):
        """
        Add a new node to the list of nodes
        :param address: <str> Address of node. Eg. 'http://192.168.0.5:5000'
        :return: None
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)


    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid
        :param chain: <list> A blockchain
        :return: <bool> True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1
        tempUTXO = dict() # maps self.hash(transaction) -> transaction

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            # Check that senders possess the products they're sending

            for transaction in block['transactions']:
                # Check the signature
                if not self.valid_signature(transaction):
                    return False

                # Transactions from the base address are all accepted by default
                if transaction['sender']==Blockchain.baseAddress:
                    tempUTXO[self.hash(transaction)] = transaction

                else:
                    input = transaction["transaction_input"]

                    if input in tempUTXO:
                        if tempUTXO[input]["recipient"] == transaction["sender"] \
                        and tempUTXO[input]["batchID"] == transaction["batchID"]:
                            tempUTXO.pop(input)
                            tempUTXO[self.hash(transaction)] = transaction

                        else:
                            print(f"hash(transaction) : invalid transaction_input.")
                            return False

                    else:
                        print(f"hash(transaction) : transaction_input isn't an UTXO")
                        return False

            last_block = block
            current_index += 1

        return True


    def resolve_conflicts(self):
        """
        This is our Consensus Algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.
        :return: <bool> True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None
        max_node = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
                    max_node = node

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            new_utxo = requests.get(f'http://{node}/utxo').json()['utxo']
            self.chain = new_chain
            self.UTXO = new_utxo
            return True
        return False


    def get_history(self, batchID):
        """Returns a list that contains the unordered history of
        transactions for a given batchID.

        :param batchID: <int>
        :return history: <list> list of transaction with the correct batchID
        """

        history = []

        for block in self.chain:
            for transaction in block['transactions']:
                if transaction['batchID'] == batchID:
                    history.append(transaction)
        return history





# Instantiate our Node
app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
@cross_origin()
def mine():
    # We run the proof of work algorithm to get the next proof...
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Forge the new Block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'merkleroot': block['merkleroot'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

@app.route('/transactions/input', methods=['POST'])
@cross_origin()
def get_input_transaction():
    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ['sender', 'recipient', 'batchID']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # get the transaction input
    try:
        index = blockchain.get_input_transaction(values['sender'], values['recipient'], values['batchID'])
        response = {'transaction_input': index}
        return jsonify(response), 200
    except Exception as e:
        return e.message, 400


@app.route('/transactions/new', methods=['POST'])
@cross_origin()
def new_transaction():
    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ['sender', 'recipient', 'batchID', 'transaction_input', 'signature']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new Transaction
    try:
        index = blockchain.new_transaction(values['sender'], values['recipient'], values['batchID'], values['transaction_input'], values['signature'])
        response = {'message': f'Transaction will be added to Block {index}'}
        return jsonify(response), 201
    except Exception as e:
        return e.message, 400

@app.route('/chain', methods=['GET'])
@cross_origin()
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/utxo', methods=['GET'])
@cross_origin()
def utxo():
    response = {
        'utxo': blockchain.UTXO,
    }
    return jsonify(response), 200




@app.route('/nodes/register', methods=['POST'])
@cross_origin()
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
@cross_origin()
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


@app.route('/validity', methods=['GET'])
@cross_origin()
def validity():
    is_valid = blockchain.valid_chain(blockchain.chain)
    return jsonify({'message':is_valid}), 200


@app.route('/history', methods=['POST'])
def history():
    values = request.get_json()

    batchID = values.get('batchID')
    if batchID is None:
        return "Error: Please supply a valid batchID", 400
    elif type(batchID) is not int:
        return "Error: Please supply an integer", 400

    history = blockchain.get_history(batchID)

    return jsonify({'history': history}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)